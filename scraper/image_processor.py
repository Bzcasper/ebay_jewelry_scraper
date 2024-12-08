# scraper/image_processor.py

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import torch
import torchvision.transforms as transforms
import torchvision.transforms.functional as TF
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from concurrent.futures import ThreadPoolExecutor
import albumentations as A

class JewelryImageProcessor:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Setup augmentation pipelines optimized for jewelry
        self.jewelry_transforms = A.Compose([
            # Luminance adjustments for shiny objects
            A.RandomBrightnessContrast(
                brightness_limit=0.2,
                contrast_limit=0.2,
                p=0.7
            ),
            # Color adjustments for metals and gems
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=30,
                val_shift_limit=20,
                p=0.5
            ),
            # Sharpness adjustments for details
            A.OneOf([
                A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1.0), p=0.5),
                A.UnsharpMask(alpha=(0.2, 0.5), p=0.5),
            ], p=0.5),
            # Geometric transformations
            A.ShiftScaleRotate(
                shift_limit=0.0625,
                scale_limit=0.1,
                rotate_limit=15,
                border_mode=cv2.BORDER_CONSTANT,
                p=0.5
            )
        ])
        
        # Setup model-specific transforms
        self.resnet_transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        self.llava_transform = transforms.Compose([
            transforms.Resize(512),
            transforms.CenterCrop(512),
            transforms.ToTensor()
        ])

    def process_image(self, image_path: Path, category: str) -> Dict[str, Image.Image]:
        """Process single image for both models with quality checks."""
        try:
            # Load and validate image
            img = Image.open(image_path).convert('RGB')
            if not self._check_image_quality(img):
                return None
            
            # Process for ResNet-50
            resnet_img = self._process_for_resnet(img)
            
            # Process for LLaVA
            llava_img = self._process_for_llava(img)
            
            # Category-specific processing
            if category in ['ring', 'earring']:
                resnet_img = self._enhance_small_details(resnet_img)
                llava_img = self._enhance_small_details(llava_img)
            elif category in ['necklace', 'bracelet']:
                resnet_img = self._enhance_metal_shine(resnet_img)
                llava_img = self._enhance_metal_shine(llava_img)
            
            return {
                'resnet': resnet_img,
                'llava': llava_img
            }
            
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {e}")
            return None

    def _check_image_quality(self, img: Image.Image) -> bool:
        """Check if image meets quality standards."""
        try:
            # Check size
            if img.size[0] < 200 or img.size[1] < 200:
                return False
            
            # Check aspect ratio
            aspect_ratio = img.size[0] / img.size[1]
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return False
            
            # Convert to numpy for analysis
            img_array = np.array(img)
            
            # Check brightness
            brightness = np.mean(img_array)
            if brightness < 20 or brightness > 235:
                return False
            
            # Check contrast
            contrast = np.std(img_array)
            if contrast < 20:
                return False
            
            # Check blur
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 100:  # Blurry image
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking image quality: {e}")
            return False

    def _process_for_resnet(self, img: Image.Image) -> Image.Image:
        """Process image for ResNet-50 training."""
        # Apply jewelry-specific augmentations
        img_array = np.array(img)
        augmented = self.jewelry_transforms(image=img_array)
        aug_img = Image.fromarray(augmented['image'])
        
        # Apply ResNet transforms
        tensor_img = self.resnet_transform(aug_img)
        
        # Convert back to PIL
        return transforms.ToPILImage()(tensor_img)

    def _process_for_llava(self, img: Image.Image) -> Image.Image:
        """Process image for LLaVA training."""
        # Apply jewelry-specific augmentations
        img_array = np.array(img)
        augmented = self.jewelry_transforms(image=img_array)
        aug_img = Image.fromarray(augmented['image'])
        
        # Apply LLaVA transforms
        tensor_img = self.llava_transform(aug_img)
        
        # Convert back to PIL
        return transforms.ToPILImage()(tensor_img)

    def _enhance_small_details(self, img: Image.Image) -> Image.Image:
        """Enhance small details in jewelry images."""
        # Sharpen
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)
        
        # Local contrast enhancement
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
        
        # Increase micro contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        return img

    def _enhance_metal_shine(self, img: Image.Image) -> Image.Image:
        """Enhance metal shine in jewelry images."""
        # Increase brightness of highlights
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        
        # Increase contrast for shine
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        # Fine-tune color
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.9)  # Slightly reduce color to emphasize shine
        
        return img

    def batch_process_directory(self, input_dir: Path, output_dir: Path, 
                              max_workers: int = 4) -> Dict[str, int]:
        """Process all images in directory with parallel processing."""
        stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'categories': {}
        }
        
        # Create output directories
        for model in ['resnet', 'llava']:
            (output_dir / model).mkdir(parents=True, exist_ok=True)
        
        # Process images in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for category_dir in input_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                    
                category = category_dir.name
                stats['categories'][category] = {
                    'processed': 0,
                    'successful': 0
                }
                
                for img_path in category_dir.glob('*.jpg'):
                    future = executor.submit(
                        self._process_single_image,
                        img_path,
                        category,
                        output_dir
                    )
                    futures.append((future, category))
            
            # Process results
            for future, category in futures:
                try:
                    result = future.result()
                    stats['total_processed'] += 1
                    stats['categories'][category]['processed'] += 1
                    
                    if result:
                        stats['successful'] += 1
                        stats['categories'][category]['successful'] += 1
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    stats['failed'] += 1
                    self.logger.error(f"Error processing batch: {e}")
        
        return stats

    def _process_single_image(self, img_path: Path, category: str,
                            output_dir: Path) -> bool:
        """Process single image and save results."""
        try:
            # Process image
            results = self.process_image(img_path, category)
            if not results:
                return False
            
            # Save processed images
            for model, img in results.items():
                save_path = output_dir / model / category / f"{img_path.stem}_{model}.jpg"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(save_path, 'JPEG', quality=95)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing {img_path}: {e}")
            return False

    def create_augmentations(self, img: Image.Image, 
                           category: str,
                           num_augmentations: int = 3) -> List[Image.Image]:
        """Create multiple augmented versions of an image."""
        augmented_images = []
        
        for _ in range(num_augmentations):
            # Apply base augmentations
            img_array = np.array(img)
            augmented = self.jewelry_transforms(image=img_array)
            aug_img = Image.fromarray(augmented['image'])
            
            # Apply category-specific enhancements
            if category in ['ring', 'earring']:
                aug_img = self._enhance_small_details(aug_img)
            elif category in ['necklace', 'bracelet']:
                aug_img = self._enhance_metal_shine(aug_img)
            
            augmented_images.append(aug_img)
        
        return augmented_images

# Example usage:
if __name__ == '__main__':
    # Initialize processor
    config = {
        'image_size': {
            'resnet': (224, 224),
            'llava': (512, 512)
        }
    }
    
    processor = JewelryImageProcessor(config)
    
    # Process directory
    input_dir = Path('raw_images')
    output_dir = Path('processed_images')
    
    stats = processor.batch_process_directory(input_dir, output_dir)
    print("Processing Statistics:")
    print(f"Total processed: {stats['total_processed']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    
    for category, cat_stats in stats['categories'].items():
        print(f"\n{category}:")
        print(f"  Processed: {cat_stats['processed']}")
        print(f"  Successful: {cat_stats['successful']}")