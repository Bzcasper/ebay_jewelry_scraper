# scraper/data_downloader.py

import os
import json
import hashlib
import time
import logging
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from queue import Queue
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class DataDownloader:
    def __init__(self, output_dir: str, max_workers: int = 4, max_retries: int = 3):
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.max_retries = max_retries
        
        # Create output directories
        self.images_dir = self.output_dir / 'images'
        self.metadata_dir = self.output_dir / 'metadata'
        self.raw_dir = self.output_dir / 'raw_data'
        
        for directory in [self.images_dir, self.metadata_dir, self.raw_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Setup session with retries
        self.session = self._create_session()
        
        # Track downloaded URLs to avoid duplicates
        self.downloaded_urls = set()
        self.url_lock = threading.Lock()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        retries = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504, 429]
        )
        
        # Mount adapter with retries for both http and https
        adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # Set headers to mimic browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        
        return session

    def download_product_data(self, products: List[Dict]) -> List[Dict]:
        """Download all data for a list of products."""
        if not products:
            return []

        successful_products = []
        failed_urls = []

        # Create download queue
        download_queue = Queue()
        for product in products:
            download_queue.put(product)

        # Process downloads with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            while not download_queue.empty():
                product = download_queue.get()
                future = executor.submit(self._process_single_product, product)
                futures.append(future)

            # Process results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        successful_products.append(result)
                    else:
                        failed_urls.append(result.get('url', 'Unknown URL'))
                except Exception as e:
                    self.logger.error(f"Error processing product: {e}")

        # Log results
        self.logger.info(f"Successfully processed {len(successful_products)} products")
        if failed_urls:
            self.logger.warning(f"Failed to process {len(failed_urls)} URLs")
            self._save_failed_urls(failed_urls)

        return successful_products

    def _process_single_product(self, product: Dict) -> Optional[Dict]:
        """Process a single product including image downloads."""
        try:
            # Check if we've already downloaded this URL
            with self.url_lock:
                if product['url'] in self.downloaded_urls:
                    self.logger.debug(f"Skipping already downloaded URL: {product['url']}")
                    return None
                self.downloaded_urls.add(product['url'])

            # Download main product image
            main_image_path = self._download_image(
                product['image_url'], 
                category=product['category']['main_category']
            )
            if not main_image_path:
                return None

            # Update product data with local image path
            product['local_image_path'] = str(main_image_path)

            # Download gallery images if available
            if 'gallery_images' in product:
                gallery_paths = []
                for img_url in product['gallery_images']:
                    if path := self._download_image(
                        img_url,
                        category=product['category']['main_category'],
                        is_gallery=True
                    ):
                        gallery_paths.append(str(path))
                if gallery_paths:
                    product['gallery_image_paths'] = gallery_paths

            # Save metadata
            self._save_metadata(product)

            return product

        except Exception as e:
            self.logger.error(f"Error processing product {product.get('url', 'unknown')}: {e}")
            return None

    def _download_image(self, url: str, category: str, is_gallery: bool = False) -> Optional[Path]:
        """Download and save an image file."""
        try:
            # Generate unique filename
            url_hash = hashlib.md5(url.encode()).hexdigest()
            if is_gallery:
                filename = f"{url_hash}_gallery_{int(time.time())}.jpg"
            else:
                filename = f"{url_hash}.jpg"

            # Create category subdirectory
            save_dir = self.images_dir / category
            save_dir.mkdir(exist_ok=True)
            save_path = save_dir / filename

            # Check if file already exists
            if save_path.exists():
                return save_path

            # Download image
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Verify it's an image
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                self.logger.warning(f"URL {url} does not point to an image")
                return None

            # Process image
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Save image with optimization
            img.save(save_path, 'JPEG', quality=85, optimize=True)

            return save_path

        except Exception as e:
            self.logger.error(f"Error downloading image {url}: {e}")
            return None

    def _save_metadata(self, product: Dict):
        """Save product metadata to JSON file."""
        try:
            # Create unique filename based on product URL
            url_hash = hashlib.md5(product['url'].encode()).hexdigest()
            filename = f"{url_hash}.json"

            # Save to category subdirectory
            category_dir = self.metadata_dir / product['category']['main_category']
            category_dir.mkdir(exist_ok=True)
            
            save_path = category_dir / filename
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(product, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving metadata for {product.get('url', 'unknown')}: {e}")

    def _save_failed_urls(self, urls: List[str]):
        """Save failed URLs for later retry."""
        try:
            failed_path = self.output_dir / 'failed_urls.txt'
            with open(failed_path, 'a', encoding='utf-8') as f:
                for url in urls:
                    f.write(f"{url}\n")
        except Exception as e:
            self.logger.error(f"Error saving failed URLs: {e}")

    def verify_downloads(self) -> Tuple[int, int, List[str]]:
        """Verify all downloaded files and return statistics."""
        total_files = 0
        corrupted_files = 0
        corrupted_paths = []

        # Check images
        for image_path in self.images_dir.rglob('*.jpg'):
            total_files += 1
            try:
                with Image.open(image_path) as img:
                    img.verify()
            except Exception:
                corrupted_files += 1
                corrupted_paths.append(str(image_path))
                self.logger.warning(f"Corrupted image found: {image_path}")

        # Check metadata files
        for json_path in self.metadata_dir.rglob('*.json'):
            total_files += 1
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except Exception:
                corrupted_files += 1
                corrupted_paths.append(str(json_path))
                self.logger.warning(f"Corrupted metadata found: {json_path}")

        return total_files, corrupted_files, corrupted_paths

    def cleanup_corrupted_files(self):
        """Remove any corrupted files found during verification."""
        _, _, corrupted_paths = self.verify_downloads()
        
        for path in corrupted_paths:
            try:
                os.remove(path)
                self.logger.info(f"Removed corrupted file: {path}")
            except Exception as e:
                self.logger.error(f"Error removing corrupted file {path}: {e}")

    def get_download_stats(self) -> Dict:
        """Get statistics about downloaded data."""
        stats = {
            'total_products': len(list(self.metadata_dir.rglob('*.json'))),
            'total_images': len(list(self.images_dir.rglob('*.jpg'))),
            'categories': {},
            'total_size': 0
        }

        # Get category statistics
        for category_dir in self.metadata_dir.iterdir():
            if category_dir.is_dir():
                category = category_dir.name
                stats['categories'][category] = {
                    'products': len(list(category_dir.glob('*.json'))),
                    'images': len(list((self.images_dir / category).glob('*.jpg')))
                }

        # Calculate total size
        for directory in [self.images_dir, self.metadata_dir]:
            for path in directory.rglob('*'):
                if path.is_file():
                    stats['total_size'] += path.stat().st_size

        # Convert size to MB
        stats['total_size'] = round(stats['total_size'] / (1024 * 1024), 2)

        return stats