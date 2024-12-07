# scraper/data_processors.py

import os
import json
import logging
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
import pandas as pd
import numpy as np
import torch
import torchvision.transforms as transforms
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional
import hashlib
import shutil

class JewelryDatasetProcessor:
    def __init__(self, raw_data_dir: str, output_dir: str):
        self.raw_data_dir = Path(raw_data_dir)
        self.output_dir = Path(output_dir)
        
        # Create dataset directories
        self.resnet_dir = self.output_dir / 'resnet50_dataset'
        self.llava_dir = self.output_dir / 'llava_dataset'
        
        for directory in [self.resnet_dir, self.llava_dir]:
            (directory / 'images').mkdir(parents=True, exist_ok=True)
            (directory / 'metadata').mkdir(parents=True, exist_ok=True)
        
        # Image transformations for ResNet-50
        self.resnet_transforms = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Image transformations for LLaVA
        self.llava_transforms = transforms.Compose([
            transforms.Resize(512),
            transforms.CenterCrop(512),
            transforms.ToTensor()
        ])
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def process_raw_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Process all raw data into ML training datasets."""
        resnet_data = []
        llava_data = []
        
        # Process each JSON file in raw data directory
        json_files = list(self.raw_data_dir.rglob("*.json"))
        self.logger.info(f"Found {len(json_files)} raw data files to process")
        
        for json_file in tqdm(json_files, desc="Processing data files"):
            with open(json_file, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            # Process each product in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for product in products:
                    future = executor.submit(self._process_single_product, product)
                    futures.append(future)
                
                # Collect results
                for future in futures:
                    try:
                        result = future.result()
                        if result:
                            resnet_entry, llava_entry = result
                            resnet_data.append(resnet_entry)
                            llava_data.append(llava_entry)
                    except Exception as e:
                        self.logger.error(f"Error processing product: {e}")
        
        return resnet_data, llava_data

    def _process_single_product(self, product: Dict) -> Optional[Tuple[Dict, Dict]]:
        """Process a single product for both datasets."""
        try:
            # Download and process image
            image_data = self._download_and_process_image(product['image_url'])
            if not image_data:
                return None
            
            resnet_img_path, llava_img_path = image_data
            
            # Create ResNet-50 entry
            resnet_entry = {
                'image_path': str(resnet_img_path),
                'category': product['category'],
                'subcategory': product['subcategory'],
                'price': float(product['price']),
                'condition': product.get('condition', 'Unknown'),
                'label': self._get_category_label(product['category'])
            }
            
            # Create LLaVA entry with detailed caption
            llava_entry = {
                'image_path': str(llava_img_path),
                'caption': self._generate_detailed_caption(product),
                'metadata': {
                    'category': product['category'],
                    'subcategory': product['subcategory'],
                    'price': float(product['price']),
                    'condition': product.get('condition', 'Unknown'),
                    'title': product['title'],
                    'url': product['url'],
                    'shipping': product.get('shipping', 'Unknown'),
                    'seller': product.get('seller', 'Unknown'),
                }
            }
            
            return resnet_entry, llava_entry
            
        except Exception as e:
            self.logger.error(f"Error processing product {product.get('url', 'unknown')}: {e}")
            return None

    def _download_and_process_image(self, image_url: str) -> Optional[Tuple[Path, Path]]:
        """Download and process image for both datasets."""
        try:
            # Generate unique filename
            filename = hashlib.md5(image_url.encode()).hexdigest()
            
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content)).convert('RGB')
            
            # Process for ResNet-50
            resnet_img = self.resnet_transforms(image)
            resnet_path = self.resnet_dir / 'images' / f"{filename}_resnet.jpg"
            self._save_tensor_as_image(resnet_img, resnet_path)
            
            # Process for LLaVA
            llava_img = self.llava_transforms(image)
            llava_path = self.llava_dir / 'images' / f"{filename}_llava.jpg"
            self._save_tensor_as_image(llava_img, llava_path)
            
            return resnet_path, llava_path
            
        except Exception as e:
            self.logger.error(f"Error processing image {image_url}: {e}")
            return None

    def _save_tensor_as_image(self, tensor: torch.Tensor, path: Path):
        """Save a tensor as an image file."""
        # Convert tensor to PIL Image
        if tensor.shape[0] == 3:  # If normalized
            tensor = tensor * torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            tensor = tensor + torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        
        tensor = tensor.clamp(0, 1)
        image = transforms.ToPILImage()(tensor)
        image.save(str(path), quality=95, optimize=True)

    def _generate_detailed_caption(self, product: Dict) -> str:
        """Generate detailed caption for LLaVA training."""
        caption_parts = []
        
        # Basic description
        caption_parts.append(f"This is a {product['condition']} {product['category']} in the {product['subcategory']} style.")
        
        # Add price information
        caption_parts.append(f"It is priced at ${product['price']:.2f}.")
        
        # Add title details if different from basic description
        title_words = set(product['title'].lower().split())
        basic_words = set(caption_parts[0].lower().split())
        if len(title_words - basic_words) > 2:  # If title has unique information
            caption_parts.append(f"The item is described as: {product['title']}.")
        
        # Add shipping information if available
        if product.get('shipping'):
            caption_parts.append(f"Shipping details: {product['shipping']}.")
            
        return ' '.join(caption_parts)

    def _get_category_label(self, category: str) -> int:
        """Convert category to numerical label."""
        categories = ['necklace', 'pendant', 'bracelet', 'ring', 'earring', 'wristwatch']
        return categories.index(category.lower())

    def create_datasets(self):
        """Create both ResNet-50 and LLaVA datasets."""
        resnet_data, llava_data = self.process_raw_data()
        
        # Save ResNet-50 dataset
        resnet_df = pd.DataFrame(resnet_data)
        resnet_df.to_csv(self.resnet_dir / 'metadata' / 'training_data.csv', index=False)
        
        # Create train/val/test splits for ResNet-50
        self._create_resnet_splits(resnet_df)
        
        # Save LLaVA dataset
        with open(self.llava_dir / 'metadata' / 'training_data.json', 'w', encoding='utf-8') as f:
            json.dump(llava_data, f, indent=2)
        
        # Create train/val/test splits for LLaVA
        self._create_llava_splits(llava_data)
        
        # Generate dataset statistics
        self._generate_dataset_stats(resnet_data, llava_data)

    def _create_resnet_splits(self, df: pd.DataFrame):
        """Create train/val/test splits for ResNet-50."""
        # Stratify by category to ensure balanced splits
        from sklearn.model_selection import train_test_split
        
        # First split: 80% train, 20% temp
        train_df, temp_df = train_test_split(
            df, test_size=0.2, stratify=df['label'], random_state=42
        )
        
        # Second split: 50% val, 50% test from temp
        val_df, test_df = train_test_split(
            temp_df, test_size=0.5, stratify=temp_df['label'], random_state=42
        )
        
        # Save splits
        splits = {
            'train': train_df,
            'val': val_df,
            'test': test_df
        }
        
        for split_name, split_df in splits.items():
            split_df.to_csv(
                self.resnet_dir / 'metadata' / f'{split_name}_data.csv',
                index=False
            )

    def _create_llava_splits(self, data: List[Dict]):
        """Create train/val/test splits for LLaVA."""
        # Group by category for stratified splitting
        category_groups = {}
        for item in data:
            category = item['metadata']['category']
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(item)
        
        train_data, val_data, test_data = [], [], []
        
        # Split each category maintaining ratios
        for category_items in category_groups.values():
            n_items = len(category_items)
            n_test = int(0.1 * n_items)
            n_val = int(0.1 * n_items)
            
            # Randomly shuffle items
            np.random.shuffle(category_items)
            
            test_data.extend(category_items[:n_test])
            val_data.extend(category_items[n_test:n_test + n_val])
            train_data.extend(category_items[n_test + n_val:])
        
        # Save splits
        splits = {
            'train': train_data,
            'val': val_data,
            'test': test_data
        }
        
        for split_name, split_data in splits.items():
            with open(self.llava_dir / 'metadata' / f'{split_name}_data.json', 'w') as f:
                json.dump(split_data, f, indent=2)

    def _generate_dataset_stats(self, resnet_data: List[Dict], llava_data: List[Dict]):
        """Generate and save dataset statistics."""
        stats = {
            'resnet50': {
                'total_images': len(resnet_data),
                'category_distribution': self._get_category_distribution(resnet_data),
                'price_stats': self._get_price_stats(resnet_data),
                'image_size': '224x224',
                'normalization': {
                    'mean': [0.485, 0.456, 0.406],
                    'std': [0.229, 0.224, 0.225]
                }
            },
            'llava': {
                'total_images': len(llava_data),
                'caption_stats': self._get_caption_stats(llava_data),
                'category_distribution': self._get_category_distribution(
                    [item['metadata'] for item in llava_data]
                ),
                'image_size': '512x512'
            }
        }
        
        # Save stats
        with open(self.output_dir / 'dataset_stats.json', 'w') as f:
            json.dump(stats, f, indent=2)

    def _get_category_distribution(self, data: List[Dict]) -> Dict[str, int]:
        """Calculate category distribution."""
        distribution = {}
        for item in data:
            category = item.get('category') or item.get('metadata', {}).get('category')
            if category:
                distribution[category] = distribution.get(category, 0) + 1
        return distribution

    def _get_price_stats(self, data: List[Dict]) -> Dict[str, float]:
        """Calculate price statistics."""
        prices = [item['price'] for item in data]
        return {
            'min': min(prices),
            'max': max(prices),
            'mean': np.mean(prices),
            'median': np.median(prices),
            'std': np.std(prices)
        }

    def _get_caption_stats(self, data: List[Dict]) -> Dict[str, Union[int, float]]:
        """Calculate caption statistics."""
        lengths = [len(item['caption'].split()) for item in data]
        return {
            'min_length': min(lengths),
            'max_length': max(lengths),
            'mean_length': np.mean(lengths),
            'median_length': np.median(lengths),
            'total_captions': len(lengths)
        }