# scraper/dataset_creator.py

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from PIL import Image
import torch
import torchvision.transforms as transforms
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import shutil
import random
from sklearn.model_selection import train_test_split

class JewelryDatasetCreator:
    def __init__(self, config: Dict):
        self.config = config
        self.output_dir = Path(config['output_dir'])
        
        # Create dataset directories
        self.resnet_dir = self.output_dir / 'resnet50_dataset'
        self.llava_dir = self.output_dir / 'llava_dataset'
        
        for dataset_dir in [self.resnet_dir, self.llava_dir]:
            for split in ['train', 'val', 'test']:
                (dataset_dir / split / 'images').mkdir(parents=True, exist_ok=True)
                
        # Setup transforms for both models
        self.resnet_transforms = {
            'train': transforms.Compose([
                transforms.Resize(256),
                transforms.RandomCrop(224),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(15),
                transforms.ColorJitter(brightness=0.2, contrast=0.2),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                  std=[0.229, 0.224, 0.225])
            ]),
            'val': transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                  std=[0.229, 0.224, 0.225])
            ])
        }
        
        self.llava_transforms = {
            'train': transforms.Compose([
                transforms.Resize(512),
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(15),
                transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
                transforms.ToTensor()
            ]),
            'val': transforms.Compose([
                transforms.Resize(512),
                transforms.ToTensor()
            ])
        }
        
        self.logger = logging.getLogger(__name__)

    def create_datasets(self, raw_data_dir: Path) -> Tuple[Dict, Dict]:
        """Create both ResNet-50 and LLaVA datasets from raw data."""
        # Load and preprocess raw data
        self.logger.info("Loading raw data...")
        product_data = self._load_raw_data(raw_data_dir)
        
        # Split data
        train_data, val_data, test_data = self._split_data(product_data)
        
        # Process for each model
        self.logger.info("Creating ResNet-50 dataset...")
        resnet_stats = self._create_resnet_dataset(train_data, val_data, test_data)
        
        self.logger.info("Creating LLaVA dataset...")
        llava_stats = self._create_llava_dataset(train_data, val_data, test_data)
        
        return resnet_stats, llava_stats

    def _load_raw_data(self, raw_data_dir: Path) -> List[Dict]:
        """Load and validate raw scraped data."""
        all_data = []
        
        # Process each JSON file
        for json_file in raw_data_dir.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Validate data entries
                valid_data = [
                    item for item in data
                    if self._validate_product_data(item)
                ]
                all_data.extend(valid_data)
                
            except Exception as e:
                self.logger.error(f"Error loading {json_file}: {e}")
                
        return all_data

    def _validate_product_data(self, item: Dict) -> bool:
        """Validate product data entry."""
        required_fields = ['image_url', 'category', 'title', 'price']
        if not all(field in item for field in required_fields):
            return False
            
        # Validate image exists
        if not Path(item['local_image_path']).exists():
            return False
            
        return True

    def _split_data(self, data: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Split data into train/val/test sets with stratification."""
        # First split: train vs rest
        train_data, temp_data = train_test_split(
            data,
            test_size=0.3,
            stratify=[d['category']['main_category'] for d in data],
            random_state=42
        )
        
        # Second split: val vs test
        val_data, test_data = train_test_split(
            temp_data,
            test_size=0.5,
            stratify=[d['category']['main_category'] for d in temp_data],
            random_state=42
        )
        
        return train_data, val_data, test_data

    def _create_resnet_dataset(self, train_data: List[Dict], val_data: List[Dict], 
                             test_data: List[Dict]) -> Dict:
        """Create ResNet-50 classification dataset."""
        stats = {
            'train_samples': 0,
            'val_samples': 0,
            'test_samples': 0,
            'class_distribution': {}
        }
        
        # Process each split
        for split_name, split_data in [
            ('train', train_data),
            ('val', val_data),
            ('test', test_data)
        ]:
            split_dir = self.resnet_dir / split_name
            transform = self.resnet_transforms[
                'train' if split_name == 'train' else 'val'
            ]
            
            # Process images
            for item in tqdm(split_data, desc=f"Processing {split_name} split"):
                try:
                    # Load and transform image
                    img_path = Path(item['local_image_path'])
                    img = Image.open(img_path).convert('RGB')
                    
                    # Apply transforms and save
                    transformed_img = transform(img)
                    output_path = split_dir / 'images' / f"{img_path.stem}_resnet.jpg"
                    self._save_tensor_as_image(transformed_img, output_path)
                    
                    # Update stats
                    stats[f'{split_name}_samples'] += 1
                    category = item['category']['main_category']
                    stats['class_distribution'][category] = \
                        stats['class_distribution'].get(category, 0) + 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing {img_path}: {e}")
                    continue
            
            # Create split CSV file
            df = pd.DataFrame([{
                'image_path': str((split_dir / 'images' / f"{Path(d['local_image_path']).stem}_resnet.jpg").relative_to(self.resnet_dir)),
                'category': d['category']['main_category'],
                'subcategory': d['category']['subcategory'],
                'label': self._get_category_label(d['category']['main_category'])
            } for d in split_data])
            
            df.to_csv(split_dir / f'{split_name}_data.csv', index=False)
        
        return stats

    def _create_llava_dataset(self, train_data: List[Dict], val_data: List[Dict], 
                            test_data: List[Dict]) -> Dict:
        """Create LLaVA dataset with detailed captions."""
        stats = {
            'train_samples': 0,
            'val_samples': 0,
            'test_samples': 0,
            'caption_stats': {
                'min_length': float('inf'),
                'max_length': 0,
                'avg_length': 0
            }
        }
        
        # Process each split
        for split_name, split_data in [
            ('train', train_data),
            ('val', val_data),
            ('test', test_data)
        ]:
            split_dir = self.llava_dir / split_name
            transform = self.llava_transforms[
                'train' if split_name == 'train' else 'val'
            ]
            
            split_entries = []
            caption_lengths = []
            
            # Process images
            for item in tqdm(split_data, desc=f"Processing {split_name} split"):
                try:
                    # Load and transform image
                    img_path = Path(item['local_image_path'])
                    img = Image.open(img_path).convert('RGB')
                    
                    # Apply transforms and save
                    transformed_img = transform(img)
                    output_path = split_dir / 'images' / f"{img_path.stem}_llava.jpg"
                    self._save_tensor_as_image(transformed_img, output_path)
                    
                    # Generate detailed caption
                    caption = self._generate_detailed_caption(item)
                    
                    # Create dataset entry
                    entry = {
                        'image_path': str(output_path.relative_to(self.llava_dir)),
                        'caption': caption,
                        'metadata': {
                            'category': item['category']['main_category'],
                            'subcategory': item['category']['subcategory'],
                            'price': item['price'],
                            'title': item['title']
                        }
                    }
                    split_entries.append(entry)
                    
                    # Update stats
                    stats[f'{split_name}_samples'] += 1
                    caption_lengths.append(len(caption.split()))
                    
                except Exception as e:
                    self.logger.error(f"Error processing {img_path}: {e}")
                    continue
            
            # Save split data
            with open(split_dir / f'{split_name}_data.json', 'w', encoding='utf-8') as f:
                json.dump(split_entries, f, indent=2)
        
        # Update caption stats
        if caption_lengths:
            stats['caption_stats']['min_length'] = min(caption_lengths)
            stats['caption_stats']['max_length'] = max(caption_lengths)
            stats['caption_stats']['avg_length'] = sum(caption_lengths) / len(caption_lengths)
        
        return stats

    def _generate_detailed_caption(self, item: Dict) -> str:
        """Generate detailed caption for LLaVA training."""
        parts = []
        
        # Basic description
        parts.append(f"This is a {item['category']['subcategory']} style "
                    f"{item['category']['main_category']} priced at ${item['price']:.2f}.")
        
        # Add material information if available
        if 'material' in item:
            parts.append(f"It is made of {item['material']}.")
            
        # Add condition if available
        if 'condition' in item:
            parts.append(f"The item is in {item['condition']} condition.")
            
        # Add specific details from title
        important_words = [w for w in item['title'].split() 
                         if len(w) > 3 and w.lower() not in parts[0].lower()]
        if important_words:
            details = ' '.join(important_words[:5])  # Limit to first 5 important words
            parts.append(f"Notable features include: {details}.")
        
        return ' '.join(parts)

    def _get_category_label(self, category: str) -> int:
        """Convert category to numerical label."""
        categories = ['necklace', 'pendant', 'bracelet', 'ring', 'earring', 'wristwatch']
        return categories.index(category.lower())

    def _save_tensor_as_image(self, tensor: torch.Tensor, path: Path):
        """Save a tensor as an image file."""
        if tensor.shape[0] == 3:  # If normalized
            tensor = tensor * torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            tensor = tensor + torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        
        tensor = tensor.clamp(0, 1)
        img = transforms.ToPILImage()(tensor)
        img.save(str(path), quality=95, optimize=True)