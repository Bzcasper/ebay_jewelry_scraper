# scraper/data_validator.py

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import json
from PIL import Image
import numpy as np
import pandas as pd
from collections import defaultdict
import hashlib
import requests
from urllib.parse import urlparse

class DataValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize validation rules
        self.price_pattern = re.compile(r'^\$?\d+\.?\d*$')
        self.title_min_length = 10
        self.title_max_length = 200
        
        # Material keywords for validation
        self.valid_materials = {
            'gold': ['14k', '18k', '24k', 'yellow gold', 'white gold', 'rose gold'],
            'silver': ['sterling', '925', 'silver'],
            'platinum': ['platinum', 'plat'],
            'gems': ['diamond', 'ruby', 'sapphire', 'emerald', 'pearl']
        }
        
        # Initialize error tracking
        self.validation_errors = defaultdict(list)

    def validate_product_data(self, product: Dict) -> Tuple[bool, List[str]]:
        """Validate complete product data entry."""
        errors = []
        
        # Check required fields
        required_fields = ['title', 'price', 'image_url', 'category']
        for field in required_fields:
            if field not in product:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return False, errors
            
        # Validate individual fields
        validators = {
            'title': self.validate_title,
            'price': self.validate_price,
            'image_url': self.validate_url,
            'category': self.validate_category
        }
        
        for field, validator in validators.items():
            if not validator(product[field]):
                errors.append(f"Invalid {field}: {product[field]}")
        
        # Validate material consistency
        if 'material' in product and 'title' in product:
            if not self._check_material_consistency(product['material'], product['title']):
                errors.append("Material inconsistent with title description")
        
        # Track errors
        if errors:
            self.validation_errors[product.get('url', 'unknown')].extend(errors)
            
        return len(errors) == 0, errors

    def validate_title(self, title: str) -> bool:
        """Validate product title."""
        if not isinstance(title, str):
            return False
            
        # Check length
        if len(title) < self.title_min_length or len(title) > self.title_max_length:
            return False
            
        # Check for basic formatting
        if not re.match(r'^[A-Za-z0-9].*[A-Za-z0-9]$', title):
            return False
            
        # Check for excessive punctuation
        if len(re.findall(r'[!?.]', title)) > 3:
            return False
            
        return True

    def validate_price(self, price: Union[str, float]) -> bool:
        """Validate price value and format."""
        if isinstance(price, str):
            if not self.price_pattern.match(price):
                return False
            try:
                price = float(price.replace('$', ''))
            except ValueError:
                return False
                
        if not isinstance(price, (int, float)):
            return False
            
        # Check reasonable range
        if price <= 0 or price > 1000000:  # Adjust max price as needed
            return False
            
        return True

    def validate_url(self, url: str) -> bool:
        """Validate URL format and accessibility."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def validate_category(self, category: Dict) -> bool:
        """Validate category structure and values."""
        required_keys = ['main_category', 'subcategory']
        if not all(key in category for key in required_keys):
            return False
            
        valid_categories = {
            'necklace': ['choker', 'pendant', 'chain'],
            'pendant': ['heart', 'cross', 'star'],
            'bracelet': ['tennis', 'charm', 'bangle'],
            'ring': ['engagement', 'wedding', 'fashion'],
            'earring': ['stud', 'hoop', 'drop'],
            'wristwatch': ['analog', 'digital', 'smart']
        }
        
        main_cat = category['main_category'].lower()
        sub_cat = category['subcategory'].lower()
        
        if main_cat not in valid_categories:
            return False
            
        if sub_cat not in valid_categories[main_cat]:
            return False
            
        return True

    def validate_image_file(self, image_path: Path) -> Tuple[bool, Optional[str]]:
        """Validate image file format and quality."""
        try:
            with Image.open(image_path) as img:
                # Check format
                if img.format not in ['JPEG', 'PNG']:
                    return False, "Invalid image format"
                
                # Check size
                if img.size[0] < 200 or img.size[1] < 200:
                    return False, "Image too small"
                
                # Check aspect ratio
                aspect_ratio = img.size[0] / img.size[1]
                if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                    return False, "Invalid aspect ratio"
                
                # Check mode
                if img.mode not in ['RGB', 'RGBA']:
                    return False, "Invalid color mode"
                
                # Check file size
                if image_path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                    return False, "File too large"
                
                return True, None
                
        except Exception as e:
            return False, str(e)

    def validate_dataset_structure(self, dataset_path: Path) -> Tuple[bool, List[str]]:
        """Validate dataset directory structure and contents."""
        errors = []
        
        # Check required directories
        required_dirs = ['images', 'metadata']
        for dir_name in required_dirs:
            dir_path = dataset_path / dir_name
            if not dir_path.exists() or not dir_path.is_dir():
                errors.append(f"Missing required directory: {dir_name}")
        
        if errors:
            return False, errors
            
        # Validate image files
        image_dir = dataset_path / 'images'
        for img_path in image_dir.rglob('*.*'):
            if img_path.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                errors.append(f"Invalid image file: {img_path}")
                continue
                
            is_valid, error = self.validate_image_file(img_path)
            if not is_valid:
                errors.append(f"Invalid image {img_path}: {error}")
        
        # Validate metadata files
        metadata_dir = dataset_path / 'metadata'
        for json_path in metadata_dir.glob('*.json'):
            try:
                with open(json_path) as f:
                    data = json.load(f)
                    
                if not isinstance(data, (dict, list)):
                    errors.append(f"Invalid metadata format in {json_path}")
                    
            except Exception as e:
                errors.append(f"Error reading metadata {json_path}: {e}")
        
        return len(errors) == 0, errors

    def clean_product_data(self, product: Dict) -> Dict:
        """Clean and standardize product data."""
        cleaned = product.copy()
        
        # Clean title
        if 'title' in cleaned:
            cleaned['title'] = self._clean_title(cleaned['title'])
        
        # Clean price
        if 'price' in cleaned:
            cleaned['price'] = self._clean_price(cleaned['price'])
        
        # Clean category
        if 'category' in cleaned:
            cleaned['category'] = self._clean_category(cleaned['category'])
        
        # Clean material
        if 'material' in cleaned:
            cleaned['material'] = self._clean_material(cleaned['material'])
        
        # Remove empty fields
        cleaned = {k: v for k, v in cleaned.items() if v is not None and v != ''}
        
        return cleaned

    def _clean_title(self, title: str) -> str:
        """Clean and standardize product title."""
        if not isinstance(title, str):
            return ''
            
        # Remove excessive whitespace
        title = ' '.join(title.split())
        
        # Remove special characters
        title = re.sub(r'[^\w\s\-.,]', '', title)
        
        # Capitalize first letter
        title = title.capitalize()
        
        return title

    def _clean_price(self, price: Union[str, float]) -> Optional[float]:
        """Clean and standardize price value."""
        if isinstance(price, str):
            # Remove currency symbols and spaces
            price = price.replace('$', '').replace(',', '').strip()
            try:
                price = float(price)
            except ValueError:
                return None
                
        if not isinstance(price, (int, float)):
            return None
            
        return round(float(price), 2)

    def _clean_category(self, category: Dict) -> Dict:
        """Clean and standardize category values."""
        cleaned = {}
        
        if 'main_category' in category:
            cleaned['main_category'] = category['main_category'].lower().strip()
            
        if 'subcategory' in category:
            cleaned['subcategory'] = category['subcategory'].lower().strip()
            
        return cleaned

    def _clean_material(self, material: str) -> str:
        """Clean and standardize material description."""
        material = material.lower().strip()
        
        # Standardize gold descriptions
        material = re.sub(r'(\d+)\s*k\s*gold', r'\1k gold', material)
        material = material.replace('karat', 'k')
        
        # Standardize silver descriptions
        material = material.replace('sterling silver', '925 silver')
        
        return material

    def _check_material_consistency(self, material: str, title: str) -> bool:
        """Check if material matches title description."""
        material = material.lower()
        title = title.lower()
        
        # Check for common inconsistencies
        if 'gold' in material and 'silver' in title:
            return False
        if 'silver' in material and 'gold' in title:
            return False
        if 'platinum' in material and ('gold' in title or 'silver' in title):
            return False
            
        return True

    def get_validation_report(self) -> Dict:
        """Generate validation error report."""
        report = {
            'total_errors': sum(len(errors) for errors in self.validation_errors.values()),
            'error_by_type': defaultdict(int),
            'urls_with_errors': len(self.validation_errors),
            'detailed_errors': dict(self.validation_errors)
        }
        
        # Count error types
        for errors in self.validation_errors.values():
            for error in errors:
                error_type = error.split(':')[0]
                report['error_by_type'][error_type] += 1
                
        return report

    def check_duplicates(self, products: List[Dict]) -> List[Tuple[str, str]]:
        """Check for duplicate products."""
        duplicates = []
        seen_hashes = {}
        
        for product in products:
            # Create hash of key product details
            hash_string = f"{product.get('title', '')}{product.get('price', '')}"
            hash_value = hashlib.md5(hash_string.encode()).hexdigest()
            
            if hash_value in seen_hashes:
                duplicates.append((
                    product.get('url', 'unknown'),
                    seen_hashes[hash_value]
                ))
            else:
                seen_hashes[hash_value] = product.get('url', 'unknown')
                
        return duplicates

# Example usage:
if __name__ == '__main__':
    validator = DataValidator()
    
    # Validate product data
    product = {
        'title': 'Beautiful Silver Ring with Diamonds',
        'price': '$199.99',
        'image_url': 'https://example.com/ring.jpg',
        'category': {
            'main_category': 'ring',
            'subcategory': 'fashion'
        },
        'material': 'sterling silver'
    }
    
    is_valid, errors = validator.validate_product_data(product)
    if is_valid:
        # Clean data
        cleaned_product = validator.clean_product_data(product)
        print("Cleaned product:", json.dumps(cleaned_product, indent=2))
    else:
        print("Validation errors:", errors)