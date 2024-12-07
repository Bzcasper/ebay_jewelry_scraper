# scraper/data_processors.py
import os
import json
import logging
import requests
from PIL import Image
from io import BytesIO
import pandas as pd
from pathlib import Path
import numpy as np
from tqdm import tqdm
import torchvision.transforms as transforms
import zipfile
import shutil

class DatasetProcessor:
    def __init__(self, base_dir="jewelry_dataset"):
        self.base_dir = Path(base_dir)
        self.images_dir = self.base_dir / "processed_images"
        self.metadata_dir = self.base_dir / "metadata"
        self.raw_html_dir = self.base_dir / "raw_html"
        self.dataset_dir = self.base_dir / "training_dataset"
        self.processed_images_dir = self.base_dir / "processed_images"
        
        # Create directories
        for dir_path in [self.images_dir, self.metadata_dir, self.raw_html_dir, self.processed_images_dir, self.dataset_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Image processing pipeline for ResNet50
        self.resnet_transforms = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Image processing for LLaVA (keeping original aspect ratio and augmenting)
        self.llava_transforms = transforms.Compose([
            transforms.Resize(512),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
        ])

    def process_image(self, image_url, item_data, retries=3, timeout=10):
        """Download and process image for both ResNet50 and LLaVA with augmentation"""
        try:
            for attempt in range(retries):
                try:
                    # Download image
                    response = requests.get(image_url, timeout=timeout)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert('RGB')
                    
                    # Generate unique filename
                    filename = f"{item_data['category']}_{item_data['subcategory']}_{hash(image_url)}"
                    
                    # Save original high-quality image for LLaVA
                    llava_path = self.processed_images_dir / f"{filename}_llava.jpg"
                    image.save(str(llava_path), 'JPEG', quality=95)
                    
                    # Process and save ResNet version with augmentation
                    resnet_path = self.processed_images_dir / f"{filename}_resnet.jpg"
                    resnet_img = self.resnet_transforms(image)
                    transforms.ToPILImage()(resnet_img).save(str(resnet_path))
                    
                    # Update item_data with image paths
                    item_data['llava_image_path'] = str(llava_path)
                    item_data['resnet_image_path'] = str(resnet_path)
                    item_data['image_width'] = image.width
                    item_data['image_height'] = image.height
                    item_data['aspect_ratio'] = image.width / image.height
                    
                    return True
                except Exception as e:
                    logging.warning(f"Attempt {attempt + 1} failed to download/process image: {e}")
                    time.sleep(2)
            logging.error(f"Failed to download/process image after {retries} attempts: {image_url}")
            return False

        except Exception as e:
            logging.error(f"Error processing image {image_url}: {e}")
            return False

    def clean_text(self, text):
        """Clean and normalize text data"""
        if not text:
            return ""
        
        # Remove special characters and normalize spacing
        cleaned = ' '.join(text.split())
        return cleaned.strip()

    def extract_price(self, price_text):
        """Extract numerical price from text"""
        if not price_text:
            return None
            
        try:
            # Remove currency symbols and convert to float
            price = ''.join(c for c in price_text if c.isdigit() or c == '.')
            return float(price)
        except:
            return None

    def process_item(self, item_data):
        """Process a single item's data and images"""
        try:
            # Process image
            if not self.process_image(item_data['image_url'], item_data):
                return None
                
            # Clean and structure metadata
            processed_data = {
                'id': hash(item_data['url']),
                'category': self.clean_text(item_data['category']),
                'subcategory': self.clean_text(item_data['subcategory']),
                'title': self.clean_text(item_data['title']),
                'price': self.extract_price(item_data['price']),
                'condition': self.clean_text(item_data.get('condition', '')),
                'description': self.clean_text(item_data.get('description', '')),
                'url': item_data['url'],
                'llava_image_path': item_data.get('llava_image_path', ''),
                'resnet_image_path': item_data.get('resnet_image_path', ''),
                'image_width': item_data.get('image_width', 0),
                'image_height': item_data.get('image_height', 0),
                'aspect_ratio': item_data.get('aspect_ratio', 0)
            }
            
            # Generate training captions for LLaVA
            processed_data['llava_captions'] = [
                f"This is a {processed_data['category']} {processed_data['subcategory']} jewelry piece. "
                f"It is {processed_data['title']}. "
                f"The item is in {processed_data['condition']} condition "
                f"and costs ${processed_data['price']:.2f}.",
                
                f"A {processed_data['condition']} {processed_data['category']} jewelry item "
                f"priced at ${processed_data['price']:.2f}. "
                f"Product details: {processed_data['title']}."
            ]
            
            return processed_data
            
        except Exception as e:
            logging.error(f"Error processing item: {e}")
            return None

    def create_dataset(self, items):
        """Create training dataset from processed items"""
        processed_items = []
        
        for item in tqdm(items, desc="Processing items"):
            processed = self.process_item(item)
            if processed:
                processed_items.append(processed)
        
        # Save processed data
        if processed_items:
            # Save complete dataset
            dataset_path = self.dataset_dir / "jewelry_dataset.json"
            with open(dataset_path, 'w', encoding='utf-8') as f:
                json.dump(processed_items, f, indent=2)
            
            # Create ResNet50 training CSV
            resnet_data = [{
                'image_path': item['resnet_image_path'],
                'category': item['category'],
                'subcategory': item['subcategory'],
                'price': item['price']
            } for item in processed_items]
            
            resnet_df = pd.DataFrame(resnet_data)
            resnet_df.to_csv(self.dataset_dir / "resnet50_training.csv", index=False)
            
            # Create LLaVA training format
            llava_data = []
            for item in processed_items:
                for caption in item['llava_captions']:
                    llava_data.append({
                        'image_path': item['llava_image_path'],
                        'caption': caption,
                        'metadata': {
                            'category': item['category'],
                            'price': item['price'],
                            'condition': item['condition']
                        }
                    })
            
            with open(self.dataset_dir / "llava_training.json", 'w', encoding='utf-8') as f:
                json.dump(llava_data, f, indent=2)
                
            logging.info(f"Dataset created with {len(processed_items)} items.")
            return len(processed_items)
        
        logging.warning("No processed items to create dataset.")
        return 0
