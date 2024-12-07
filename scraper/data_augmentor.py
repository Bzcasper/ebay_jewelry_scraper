# scraper/data_augmentor.py

import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import torch
import torchvision.transforms as transforms
import torchvision.transforms.functional as TF
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import albumentations as A
from tqdm import tqdm
import random

class JewelryAugmentor:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Define augmentation strength for different categories
        self.category_augment_params = {
            'ring': {'color_factor': 0.2, 'brightness_factor': 0.2},
            'necklace': {'color_factor': 0.3, 'brightness_factor': 0.3},
            'bracelet': {'color_factor': 0.2, 'brightness_factor': 0.2},
            'earring': {'color_factor': 0.3, 'brightness_factor': 0.3},
            'pendant': {'color_factor': 0.3, 'brightness_factor': 0.3},
            'wristwatch': {'color_factor': 0.2, 'brightness_factor': 0.2}
        }
        
        # Setup augmentation pipelines
        self.basic_transforms = A.Compose([
            A.HorizontalFlip(p=0.5),
            A.RandomRotate90(p=0.5),
            A.RandomBrightnessContrast(p=0.5),
            A.GaussNoise(p=0.3),
            A.OneOf([
                A.MotionBlur(blur_limit=3),
                A.MedianBlur(blur_limit=3),
                A.GaussianBlur(blur_limit=3),
            ], p=0.3),
        ])
        
        self.advanced_transforms = A.Compose([
            A.ShiftScaleRotate(
                shift_limit=0.1,
                scale_limit=0.2,
                rotate_limit=30,
                border_mode=0,
                p=0.5
            ),
            A.OneOf([
                A.HueSaturationValue(
                    hue_shift_limit=20,
                    sat_shift_limit=30,
                    val_shift_limit=20,
                    p=0.5
                ),
                A.RGBShift(
                    r_shift_limit=20,
                    g_shift_limit=20,
                    b_shift_limit=20,
                    p=0.5
                )
            ], p=0.5),
            A.RandomBrightnessContrast(
                brightness_limit=0.2,
                contrast_limit=0.2,
                p=0.5
            ),
            A.CLAHE(clip_limit=4.0, p=0.5),
        ])
        
        # Special transforms for shiny objects (like metals)
        self.metal_transforms = A.Compose([
            A.RandomBrightnessContrast(
                brightness_limit=0.3,
                contrast_limit=0.3,
                p=0.7
            ),
            A.OneOf([
                A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1.0), p=0.5),
                A.UnsharpMask(alpha=(0.2, 0.5), p=0.5),
            ], p=0.5),
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=20,
                val_shift_limit=20,
                p=0.5
            ),
        ])

    def augment_dataset(self, input_dir: Path, output_dir: Path) -> Dict:
        """Augment entire dataset with category-specific augmentations."""
        stats = {
            'total_processed': 0,
            'augmentations_created': 0,
            'failures': 0,
            'category_stats': {}
        }
        
        # Process each category directory
        for category_dir in input_dir.iterdir():
            if not category_dir.is_dir():
                continue
                
            category = category_dir.name
            category_output_dir = output_dir / category
            category_output_dir.mkdir(parents=True, exist_ok=True)
            
            category_stats = self._augment_category(
                category_dir,
                category_output_dir,
                category
            )
            
            stats['category_stats'][category] = category_stats
            stats['total_processed'] += category_stats['processed']
            stats['augmentations_created'] += category_stats['augmented']
            stats['failures'] += category_stats['failures']
            
        return stats

    def _augment_category(self, input_dir: Path, output_dir: Path, 
                         category: str) -> Dict:
        """Apply category-specific augmentations."""
        stats = {'processed': 0, 'augmented': 0, 'failures': 0}
        
        # Get category-specific parameters
        params = self.category_augment_params.get(category, {
            'color_factor': 0.2,
            'brightness_factor': 0.2
        })
        
        # Process each image
        for img_path in tqdm(list(input_dir.glob('*.jpg')), 
                           desc=f"Augmenting {category}"):
            try:
                # Load and validate image
                img = Image.open(img_path).convert('RGB')
                if not self._validate_image_quality(img):
                    continue
                
                # Create base augmentations
                augmented_images = self._create_base_augmentations(
                    img, category, params
                )
                
                # Create special augmentations based on category
                special_augmentations = self._create_special_augmentations(
                    img, category
                )
                augmented_images.extend(special_augmentations)
                
                # Save augmented images
                for idx, aug_img in enumerate(augmented_images):
                    output_path = output_dir / f"{img_path.stem}_aug_{idx}.jpg"
                    aug_img.save(output_path, 'JPEG', quality=95)
                    stats['augmented'] += 1
                
                stats['processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {img_path}: {e}")
                stats['failures'] += 1
                continue
                
        return stats

    def _create_base_augmentations(self, img: Image.Image, category: str,
                                 params: Dict) -> List[Image.Image]:
        """Create basic augmentations for an image."""
        augmented = []
        img_array = np.array(img)
        
        # Apply basic transforms
        for _ in range(2):  # Create 2 basic augmentations
            transformed = self.basic_transforms(image=img_array)
            augmented.append(Image.fromarray(transformed['image']))
        
        # Apply advanced transforms
        for _ in range(2):  # Create 2 advanced augmentations
            transformed = self.advanced_transforms(image=img_array)
            augmented.append(Image.fromarray(transformed['image']))
        
        return augmented

    def _create_special_augmentations(self, img: Image.Image,
                                    category: str) -> List[Image.Image]:
        """Create category-specific special augmentations."""
        augmented = []
        img_array = np.array(img)
        
        # Apply metal transforms for shiny objects
        if category in ['ring', 'necklace', 'bracelet']:
            for _ in range(2):  # Create 2 metal-specific augmentations
                transformed = self.metal_transforms(image=img_array)
                augmented.append(Image.fromarray(transformed['image']))
        
        # Create category-specific augmentations
        if category == 'ring':
            # Add rotation variations for rings
            angles = [45, 90, 135, 180]
            for angle in angles:
                rotated = img.rotate(angle, expand=True)
                augmented.append(rotated)
                
        elif category in ['necklace', 'bracelet']:
            # Add perspective variations for long items
            perspective_transforms = [
                A.SafeRotate(limit=30, border_mode=0),
                A.Perspective(scale=(0.05, 0.1)),
            ]
            for transform in perspective_transforms:
                transformed = transform(image=img_array)
                augmented.append(Image.fromarray(transformed['image']))
        
        return augmented

    def _validate_image_quality(self, img: Image.Image) -> bool:
        """Validate image quality for augmentation."""
        try:
            # Check minimum size
            if img.size[0] < 200 or img.size[1] < 200:
                return False
            
            # Check aspect ratio
            aspect_ratio = img.size[0] / img.size[1]
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return False
            
            # Check brightness and contrast
            img_array = np.array(img)
            brightness = np.mean(img_array)
            contrast = np.std(img_array)
            
            if brightness < 20 or brightness > 235:  # Too dark or too bright
                return False
            if contrast < 20:  # Too low contrast
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating image quality: {e}")
            return False

    def preprocess_for_training(self, img: Image.Image, 
                              model_type: str) -> torch.Tensor:
        """Preprocess image for specific model training."""
        if model_type == 'resnet':
            transform = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])
        elif model_type == 'llava':
            transform = transforms.Compose([
                transforms.Resize(512),
                transforms.ToTensor(),
            ])
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        return transform(img)