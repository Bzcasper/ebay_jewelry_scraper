# scraper/data_processors.py

import os
import logging
from PIL import Image
import requests
from io import BytesIO
from config import MAX_IMAGE_SIZE, IMAGE_QUALITY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_image(image_url: str, save_path: str) -> bool:
    """Download and process the image"""
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content))
        image = image.convert('RGB')  # Ensure image is in RGB
        image.thumbnail(MAX_IMAGE_SIZE, Image.ANTIALIAS)
        image.save(save_path, format='JPEG', quality=IMAGE_QUALITY)

        logger.info(f"Processed and saved image: {save_path}")
        return True

    except Exception as e:
        logger.error(f"Error processing image from {image_url}: {e}")
        return False

def save_metadata(items: list, metadata_dir: str, filename: str) -> None:
    """Save metadata to a JSON file"""
    import json

    try:
        filepath = os.path.join(metadata_dir, f"{filename}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=4)
        logger.info(f"Saved metadata to {filepath}")
    except Exception as e:
        logger.error(f"Error saving metadata to {filepath}: {e}")
