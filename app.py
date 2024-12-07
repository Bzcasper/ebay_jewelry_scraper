# app.py

from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from scraper.core import EbayJewelryScraper
from scraper.dataset_creator import JewelryDatasetCreator
from scraper.data_augmentor import JewelryAugmentor

app = Flask(__name__)

# Global state for scraping progress
scraping_state = {
    'status': 'idle',
    'current_category': None,
    'items_scraped': 0,
    'total_items': 0,
    'errors': [],
    'last_update': None
}

# Load and manage categories
class CategoryManager:
    def __init__(self, config_file: str = 'config/categories.json'):
        self.config_file = config_file
        self.categories = self._load_categories()
        
    def _load_categories(self) -> Dict:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            'necklace': ['Choker', 'Pendant', 'Chain'],
            'pendant': ['Heart', 'Cross', 'Star'],
            'bracelet': ['Tennis', 'Charm', 'Bangle'],
            'ring': ['Engagement', 'Wedding', 'Fashion'],
            'earring': ['Stud', 'Hoop', 'Drop'],
            'wristwatch': ['Analog', 'Digital', 'Smart']
        }
    
    def save_categories(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.categories, f, indent=2)
            
    def add_category(self, main_category: str):
        if main_category not in self.categories:
            self.categories[main_category] = []
            self.save_categories()
            
    def add_subcategory(self, main_category: str, subcategory: str):
        if main_category in self.categories and subcategory not in self.categories[main_category]:
            self.categories[main_category].append(subcategory)
            self.save_categories()
            
    def remove_category(self, main_category: str):
        if main_category in self.categories:
            del self.categories[main_category]
            self.save_categories()
            
    def remove_subcategory(self, main_category: str, subcategory: str):
        if main_category in self.categories and subcategory in self.categories[main_category]:
            self.categories[main_category].remove(subcategory)
            self.save_categories()

# Initialize category manager
category_manager = CategoryManager()

@app.route('/')
def index():
    """Render main interface."""
    return render_template('index.html', 
                         categories=category_manager.categories,
                         scraping_state=scraping_state)

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories and subcategories."""
    return jsonify(category_manager.categories)

@app.route('/api/categories', methods=['POST'])
def update_categories():
    """Add or update category/subcategory."""
    data = request.json
    try:
        if 'main_category' in data:
            if 'subcategory' in data:
                # Add subcategory
                category_manager.add_subcategory(data['main_category'], data['subcategory'])
            else:
                # Add main category
                category_manager.add_category(data['main_category'])
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/categories', methods=['DELETE'])
def delete_category():
    """Delete category or subcategory."""
    data = request.json
    try:
        if 'main_category' in data:
            if 'subcategory' in data:
                # Remove subcategory
                category_manager.remove_subcategory(data['main_category'], data['subcategory'])
            else:
                # Remove main category
                category_manager.remove_category(data['main_category'])
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/start-scraping', methods=['POST'])
def start_scraping():
    """Start scraping process for selected categories."""
    if scraping_state['status'] == 'running':
        return jsonify({'status': 'error', 'message': 'Scraping already in progress'}), 400
        
    selected_categories = request.json.get('categories', [])
    if not selected_categories:
        return jsonify({'status': 'error', 'message': 'No categories selected'}), 400
    
    # Start scraping in background thread
    thread = threading.Thread(target=run_scraping_pipeline, args=(selected_categories,))
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'Scraping started'})

def run_scraping_pipeline(selected_categories: List[Dict]):
    """Run complete scraping and dataset creation pipeline."""
    global scraping_state
    
    try:
        scraping_state.update({
            'status': 'running',
            'items_scraped': 0,
            'total_items': 0,
            'errors': [],
            'last_update': datetime.now().isoformat()
        })
        
        # Initialize components
        scraper = EbayJewelryScraper(output_dir="raw_data")
        creator = JewelryDatasetCreator(config={
            'output_dir': 'datasets',
            'resnet_size': (224, 224),
            'llava_size': (512, 512)
        })
        augmentor = JewelryAugmentor(config={
            'augmentations_per_image': 3
        })
        
        # Scrape each category
        all_products = []
        for category in selected_categories:
            scraping_state['current_category'] = category['main_category']
            
            for subcategory in category['subcategories']:
                try:
                    products = scraper.scrape_category(
                        category['main_category'],
                        subcategory
                    )
                    all_products.extend(products)
                    
                    scraping_state['items_scraped'] += len(products)
                    scraping_state['last_update'] = datetime.now().isoformat()
                    
                except Exception as e:
                    error_msg = f"Error scraping {category['main_category']}/{subcategory}: {str(e)}"
                    scraping_state['errors'].append(error_msg)
        
        # Create datasets
        if all_products:
            # Create raw datasets
            resnet_stats, llava_stats = creator.create_datasets(
                raw_data_dir=Path("raw_data")
            )
            
            # Augment training data
            augmentor.augment_dataset(
                input_dir=Path("datasets/resnet50_dataset/train"),
                output_dir=Path("datasets/resnet50_dataset/train_augmented")
            )
            
            scraping_state.update({
                'status': 'completed',
                'total_items': len(all_products),
                'resnet_stats': resnet_stats,
                'llava_stats': llava_stats,
                'last_update': datetime.now().isoformat()
            })
        else:
            raise Exception("No products were scraped successfully")
            
    except Exception as e:
        scraping_state.update({
            'status': 'error',
            'errors': [str(e)],
            'last_update': datetime.now().isoformat()
        })

@app.route('/api/scraping-status')
def get_scraping_status():
    """Get current scraping status."""
    return jsonify(scraping_state)

@app.route('/api/download-dataset/<dataset_type>')
def download_dataset(dataset_type):
    """Download specified dataset type."""
    if dataset_type not in ['resnet', 'llava']:
        return jsonify({'status': 'error', 'message': 'Invalid dataset type'}), 400
        
    try:
        dataset_path = f"datasets/{dataset_type}_dataset.zip"
        return send_file(dataset_path, as_attachment=True)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

if __name__ == '__main__':
    # Ensure required directories exist
    for directory in ['raw_data', 'datasets', 'logs', 'config']:
        os.makedirs(directory, exist_ok=True)
        
    app.run(host='0.0.0.0', port=5000, debug=True)