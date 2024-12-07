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
import time

from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class DatasetProcessor:
    base_dir: str = "jewelry_dataset"
    images_dir: Path = field(init=False)
    metadata_dir: Path = field(init=False)
    raw_html_dir: Path = field(init=False)
    dataset_dir: Path = field(init=False)
    processed_images_dir: Path = field(init=False)
    
    # Image processing pipeline for ResNet50
    resnet_transforms: transforms.Compose = field(init=False)
    
    # Image processing for LLaVA (keeping original aspect ratio and augmenting)
    llava_transforms: transforms.Compose = field(init=False)
    
    categories: List[Dict] = field(default_factory=lambda: [
        {'main_class': 'Necklace', 'subcategories': ['Choker', 'Pendant', 'Chain']},
        {'main_class': 'Pendant', 'subcategories': ['Heart', 'Cross', 'Star']},
        {'main_class': 'Bracelet', 'subcategories': ['Tennis', 'Charm', 'Bangle']},
        {'main_class': 'Ring', 'subcategories': ['Engagement', 'Wedding', 'Fashion']},
        {'main_class': 'Earring', 'subcategories': ['Stud', 'Hoop', 'Drop']},
        {'main_class': 'Wristwatch', 'subcategories': ['Analog', 'Digital', 'Smart']},
    ])
    
    proxies: List[str] = field(default_factory=lambda: [
        # Add your proxy addresses here in the format "http://ip:port"
        "http://123.456.789.0:8080",
        "http://234.567.890.1:8080",
        "http://345.678.901.2:8080",
    ])
    
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36",
    ])
    
    def __post_init__(self):
        """
        Initialize directories and image transformation pipelines.
        """
        self.base_dir = Path(self.base_dir)
        self.images_dir = self.base_dir / "processed_images"
        self.metadata_dir = self.base_dir / "metadata"
        self.raw_html_dir = self.base_dir / "raw_html"
        self.dataset_dir = self.base_dir / "training_dataset"
        self.processed_images_dir = self.base_dir / "processed_images"
        
        # Create directories if they don't exist
        for dir_path in [
            self.images_dir, 
            self.metadata_dir, 
            self.raw_html_dir, 
            self.processed_images_dir, 
            self.dataset_dir
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Define image transformations for ResNet50
        self.resnet_transforms = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # Standard ImageNet mean
                std=[0.229, 0.224, 0.225]    # Standard ImageNet std
            )
        ])
        
        # Define image transformations for LLaVA
        self.llava_transforms = transforms.Compose([
            transforms.Resize(512),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
        ])

    def process_image(self, image_url: str, item_data: Dict, retries: int = 3, timeout: int = 10) -> bool:
        """
        Download and process image for both ResNet50 and LLaVA with augmentation.
        
        Args:
            image_url (str): URL of the image to download.
            item_data (Dict): Dictionary containing item data to update with image paths.
            retries (int): Number of retries for downloading the image.
            timeout (int): Timeout for the image download request.
        
        Returns:
            bool: True if processing is successful, False otherwise.
        """
        try:
            for attempt in range(retries):
                try:
                    # Download image
                    response = requests.get(image_url, timeout=timeout)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert('RGB')
                    
                    # Generate unique filename using current timestamp and hash
                    timestamp = int(time.time() * 1000)
                    unique_hash = abs(hash(image_url)) % (10 ** 8)
                    filename = f"{timestamp}_{unique_hash}"
                    
                    # Save original high-quality image for LLaVA
                    llava_path = self.processed_images_dir / f"{filename}_llava.jpg"
                    image.save(str(llava_path), 'JPEG', quality=95)
                    
                    # Process and save ResNet version with augmentation
                    resnet_img = self.resnet_transforms(image)
                    resnet_pil = transforms.ToPILImage()(resnet_img)
                    resnet_path = self.processed_images_dir / f"{filename}_resnet.jpg"
                    resnet_pil.save(str(resnet_path))
                    
                    # Update item_data with image paths and metadata
                    item_data['llava_image_path'] = str(llava_path.resolve())
                    item_data['resnet_image_path'] = str(resnet_path.resolve())
                    item_data['image_width'], item_data['image_height'] = image.size
                    item_data['aspect_ratio'] = round(image.width / image.height, 2) if image.height != 0 else 0
                    
                    logging.info(f"Successfully processed image: {image_url}")
                    return True
                except Exception as e:
                    logging.warning(f"Attempt {attempt + 1} failed to download/process image: {e}")
                    time.sleep(2)  # Wait before retrying
            logging.error(f"Failed to download/process image after {retries} attempts: {image_url}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error in process_image: {e}")
            return False

    def clean_text(self, text: Optional[str]) -> str:
        """
        Clean and normalize text data.
        
        Args:
            text (Optional[str]): Text to clean.
        
        Returns:
            str: Cleaned text.
        """
        if not text:
            return ""
        
        # Remove special characters and normalize spacing
        cleaned = ' '.join(text.split())
        return cleaned.strip()

    def extract_price(self, price_text: str) -> Optional[float]:
        """
        Extract numerical price from text.
        
        Args:
            price_text (str): Text containing the price.
        
        Returns:
            Optional[float]: Extracted price or None if not found.
        """
        if not price_text:
            return None
            
        try:
            # Remove currency symbols and convert to float
            price = ''.join(c for c in price_text if c.isdigit() or c == '.')
            return float(price) if price else None
        except ValueError:
            logging.warning(f"Unable to extract price from text: {price_text}")
            return None

    def process_item(self, item_data: Dict) -> Optional[Dict]:
        """
        Process a single item's data and images.
        
        Args:
            item_data (Dict): Dictionary containing raw item data.
        
        Returns:
            Optional[Dict]: Processed item data or None if processing fails.
        """
        try:
            # Process image
            if not self.process_image(item_data['image_url'], item_data):
                return None
                
            # Clean and structure metadata
            processed_data = {
                'id': abs(hash(item_data['url'])) % (10 ** 8),  # Unique identifier
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

    def create_dataset(self, items: List[Dict]) -> int:
        """
        Create training dataset from processed items.
        
        Args:
            items (List[Dict]): List of processed item data.
        
        Returns:
            int: Number of items processed.
        """
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
            resnet_csv_path = self.dataset_dir / "resnet50_training.csv"
            resnet_df.to_csv(resnet_csv_path, index=False)
            
            # Create LLaVA training JSON
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
            
            llava_json_path = self.dataset_dir / "llava_training.json"
            with open(llava_json_path, 'w', encoding='utf-8') as f:
                json.dump(llava_data, f, indent=2)
                
            logging.info(f"Dataset created with {len(processed_items)} items.")
            return len(processed_items)
        
        logging.warning("No processed items to create dataset.")
        return 0
