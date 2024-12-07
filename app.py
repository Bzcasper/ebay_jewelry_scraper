# app.py
from flask import Flask, render_template, jsonify, request, send_file
import logging
from scraper.core import EbayJewelryScraper
from config import ScraperConfig
import threading
import json
import os
import zipfile
from scraper.data_processors import DatasetProcessor
from functools import wraps

app = Flask(__name__)

# Configure logging
from scraper.logger import setup_logging
setup_logging()

# Initialize configuration
scraper_config = ScraperConfig()

# Initialize scraping progress tracker
scraping_progress = {
    'status': 'idle',
    'current_class': None,
    'current_subcategory': None,
    'items_found': 0,
    'processed_items': 0,
    'error': None,
    'current_task': None
}

# Lock for thread-safe updates
progress_lock = threading.Lock()

# API Key for securing endpoints
API_KEY = os.environ.get('API_KEY', 'your-secure-api-key')

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('x-api-key')
        if key and key == API_KEY:
            return f(*args, **kwargs)
        else:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    return decorated

@app.route('/')
def index():
    return render_template('index.html', config=scraper_config)

@app.route('/config', methods=['GET'])
@require_api_key
def get_config():
    return jsonify(vars(scraper_config))

@app.route('/config', methods=['POST'])
@require_api_key
def update_config():
    try:
        data = request.get_json()
        if 'categories' in data:
            # Validate categories structure
            if isinstance(data['categories'], list):
                for cat in data['categories']:
                    if not ('main_class' in cat and 'subcategories' in cat and isinstance(cat['subcategories'], list)):
                        return jsonify({'status': 'error', 'message': 'Invalid categories structure.'}), 400
                scraper_config.categories = data['categories']
            else:
                return jsonify({'status': 'error', 'message': 'Categories should be a list.'}), 400
        if 'max_items' in data:
            max_items = int(data['max_items'])
            if max_items < 1:
                return jsonify({'status': 'error', 'message': 'max_items must be at least 1.'}), 400
            scraper_config.max_items = max_items
        if 'max_pages' in data:
            max_pages = int(data['max_pages'])
            if max_pages < 1:
                return jsonify({'status': 'error', 'message': 'max_pages must be at least 1.'}), 400
            scraper_config.max_pages = max_pages
        if 'output_dir' in data:
            output_dir = data['output_dir'].strip()
            if not output_dir:
                return jsonify({'status': 'error', 'message': 'output_dir cannot be empty.'}), 400
            scraper_config.output_dir = output_dir
        return jsonify({'status': 'success', 'config': vars(scraper_config)})
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid numerical value.'}), 400
    except Exception as e:
        logging.error(f"Error updating config: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error.'}), 500

@app.route('/categories', methods=['GET'])
@require_api_key
def get_categories():
    return jsonify(scraper_config.categories)

def run_scraper(selected_classes):
    global scraping_progress
    try:
        with progress_lock:
            scraping_progress.update({
                'status': 'running',
                'current_class': None,
                'current_subcategory': None,
                'items_found': 0,
                'processed_items': 0,
                'error': None,
                'current_task': 'Initializing scraper'
            })
        
        scraper = EbayJewelryScraper(output_dir=scraper_config.output_dir)
        processor = DatasetProcessor(base_dir=scraper_config.output_dir)
        
        for cls in selected_classes:
            category = cls['main_class']
            subcategories = cls['subcategories']
            for subcat in subcategories:
                with progress_lock:
                    scraping_progress.update({
                        'current_class': category,
                        'current_subcategory': subcat,
                        'current_task': f"Scraping {category} - {subcat}"
                    })
                items = scraper.scrape_category(
                    category=category,
                    subcategory=subcat,
                    max_items=scraper_config.max_items,
                    max_pages=scraper_config.max_pages
                )
                with progress_lock:
                    scraping_progress['items_found'] += len(items)
                processed_count = processor.create_dataset(items)
                with progress_lock:
                    scraping_progress['processed_items'] += processed_count
        
        # After scraping, create zip files
        final_zip_path = os.path.join(scraper_config.output_dir, "datasets.zip")
        with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as final_zip:
            # Zip ResNet50 dataset
            resnet_zip_path = os.path.join(scraper_config.output_dir, "resnet50_dataset.zip")
            with zipfile.ZipFile(resnet_zip_path, 'w', zipfile.ZIP_DEFLATED) as resnet_zip:
                resnet_training_csv = os.path.join(scraper_config.output_dir, "training_dataset", "resnet50_training.csv")
                resnet_zip.write(resnet_training_csv, arcname="resnet50_training.csv")
                # Add ResNet50 images
                for root, dirs, files in os.walk(os.path.join(scraper_config.output_dir, "processed_images")):
                    for file in files:
                        if "resnet" in file:
                            resnet_zip.write(os.path.join(root, file), arcname=os.path.join("images", file))
            final_zip.write(resnet_zip_path, arcname="resnet50_dataset.zip")
            os.remove(resnet_zip_path)
            
            # Zip LLaVA dataset
            llava_zip_path = os.path.join(scraper_config.output_dir, "llava_dataset.zip")
            with zipfile.ZipFile(llava_zip_path, 'w', zipfile.ZIP_DEFLATED) as llava_zip:
                llava_training_json = os.path.join(scraper_config.output_dir, "training_dataset", "llava_training.json")
                llava_zip.write(llava_training_json, arcname="llava_training.json")
                # Add LLaVA images
                for root, dirs, files in os.walk(os.path.join(scraper_config.output_dir, "processed_images")):
                    for file in files:
                        if "llava" in file:
                            llava_zip.write(os.path.join(root, file), arcname=os.path.join("images", file))
            final_zip.write(llava_zip_path, arcname="llava_dataset.zip")
            os.remove(llava_zip_path)
        
        with progress_lock:
            scraping_progress.update({
                'status': 'completed',
                'current_task': 'Scraping and dataset creation completed'
            })
    
    except Exception as e:
        logging.error(f"Scraping error: {e}")
        with progress_lock:
            scraping_progress.update({
                'status': 'error',
                'error': str(e),
                'current_task': 'Error occurred'
            })

@app.route('/start_scraping', methods=['POST'])
@require_api_key
def start_scraping():
    data = request.get_json()
    selected_classes = data.get('selected_classes')
    
    if not selected_classes:
        return jsonify({'status': 'error', 'message': 'No classes selected for scraping.'}), 400
    
    thread = threading.Thread(target=run_scraper, args=(selected_classes,))
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/progress', methods=['GET'])
@require_api_key
def get_progress():
    with progress_lock:
        return jsonify(scraping_progress)

@app.route('/download_dataset', methods=['GET'])
@require_api_key
def download_dataset():
    dataset_path = os.path.join(scraper_config.output_dir, "datasets.zip")
    if os.path.exists(dataset_path):
        return send_file(dataset_path, as_attachment=True)
    else:
        return jsonify({'status': 'error', 'message': 'Dataset not found.'}), 404

if __name__ == '__main__':
    # Ensure output directories exist
    os.makedirs(scraper_config.output_dir, exist_ok=True)
    os.makedirs(os.path.join(scraper_config.output_dir, "raw_html"), exist_ok=True)
    os.makedirs(os.path.join(scraper_config.output_dir, "processed_images"), exist_ok=True)
    os.makedirs(os.path.join(scraper_config.output_dir, "training_dataset"), exist_ok=True)
    os.makedirs(os.path.join(scraper_config.output_dir, "training_dataset", "resnet50_training"), exist_ok=True)
    os.makedirs(os.path.join(scraper_config.output_dir, "training_dataset", "llava_training"), exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
