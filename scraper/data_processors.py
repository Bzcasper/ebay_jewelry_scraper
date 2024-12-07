# scraper/data_processors.py
import os
import json
import requests
from PIL import Image
from io import BytesIO
import logging

def process_image(image_url, output_path):
    """Download and process an image"""
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # Resize if too large
        max_size = (800, 800)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
        # Save with optimization
        img.save(output_path, 'JPEG', quality=85, optimize=True)
        return True
        
    except Exception as e:
        logging.error(f"Error processing image {image_url}: {str(e)}")
        return False

def save_metadata(items, output_dir, prefix):
    """Save metadata to JSON file"""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
            
        logging.info(f"Saved metadata to {filepath}")
        return True
        
    except Exception as e:
        logging.error(f"Error saving metadata: {str(e)}")
        return False