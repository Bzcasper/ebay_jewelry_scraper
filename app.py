# app.py

import os
import logging
from pathlib import Path
from datetime import datetime
import threading
from typing import Dict, Any, Optional

from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from scraper.core import EbayJewelryScraper
from scraper.database import db, Item
from config import LOG_DIR, IMAGE_DIR, METADATA_DIR, RAW_HTML_DIR

# Configure Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create required directories using config paths
REQUIRED_DIRS = [
    LOG_DIR,
    IMAGE_DIR,
    METADATA_DIR,
    RAW_HTML_DIR
]

for directory in REQUIRED_DIRS:
    Path(directory).mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global progress tracking
scraping_progress = {
    'status': 'idle',
    'current_category': None,
    'items_found': 0,
    'error': None,
    'last_update': None
}

def update_progress(status: str, category: Optional[str] = None,
                   items: int = 0, error: Optional[str] = None) -> None:
    """Update global progress tracking"""
    global scraping_progress
    scraping_progress.update({
        'status': status,
        'current_category': category,
        'items_found': items,
        'error': error,
        'last_update': datetime.now().isoformat()
    })

def run_scraper(category: str, subcategory: str, max_items: int = 10) -> None:
    """Background task to run the scraper"""
    try:
        update_progress('running', f"{category} - {subcategory}")
        logger.info(f"Starting scrape for {category} - {subcategory}")

        # Initialize scraper with directories from config
        scraper = EbayJewelryScraper(
            output_dir=str(Path("jewelry_dataset")),
            image_dir=str(IMAGE_DIR),
            metadata_dir=str(METADATA_DIR),
            raw_html_dir=str(RAW_HTML_DIR)
        )

        # Run scraping
        items = scraper.scrape_category(category, subcategory, max_items=max_items)

        # Save to database
        saved_items = []
        for item in items:
            if saved_item := db.save_item(item):
                saved_items.append(saved_item)

        update_progress('completed', items=len(saved_items))
        logger.info(f"Completed scraping {len(saved_items)} items")

    except Exception as e:
        error_msg = f"Scraping error: {str(e)}"
        logger.error(error_msg)
        update_progress('error', error=error_msg)

@app.route('/')
def index() -> str:
    """Render main page"""
    return render_template('index.html')

@app.route('/start_scraping', methods=['POST'])
def start_scraping() -> Dict[str, Any]:
    """Start scraping process"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        category = data.get('category', 'Rings')
        subcategory = data.get('subcategory', 'Engagement')
        max_items = int(data.get('max_items', 10))

        # Validate inputs
        if not category or not subcategory:
            return jsonify({'error': 'Category and subcategory are required'}), 400

        if not 1 <= max_items <= 100:
            return jsonify({'error': 'Max items must be between 1 and 100'}), 400

        # Start scraping in background thread
        thread = threading.Thread(
            target=run_scraper,
            args=(category, subcategory, max_items)
        )
        thread.daemon = True
        thread.start()

        return jsonify({'status': 'started'})

    except Exception as e:
        error_msg = f"Error starting scraper: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/progress')
def get_progress() -> Dict[str, Any]:
    """Get current scraping progress"""
    return jsonify(scraping_progress)

@app.route('/stats')
def get_stats() -> Dict[str, Any]:
    """Get scraping statistics"""
    try:
        # Get count per category and subcategory
        counts = db.get_item_count()

        return jsonify(counts)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': 'Failed to retrieve stats'}), 500

@app.route('/recent_items')
def get_recent_items() -> Any:
    """Get most recent items"""
    try:
        # Get optional category filters
        category = request.args.get('category')
        subcategory = request.args.get('subcategory')

        # Get items from database
        items = db.get_recent_items(
            limit=10,
            category=category,
            subcategory=subcategory
        )

        # Prepare data for JSON
        recent_items = []
        for item in items:
            recent_items.append({
                'title': item.title,
                'price': f"{item.price:.2f}",
                'url': item.url,
                'image_url': item.image_url,
                'image_path': item.image_path,  # Already adjusted to /images/<filename>
                'condition': item.condition,
                'shipping': item.shipping,
                'seller': item.seller,
                'location': item.location,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })

        return jsonify(recent_items)

    except Exception as e:
        error_msg = f"Error getting recent items: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/images/<path:filename>')
def serve_image(filename: str) -> Any:
    """Serve scraped images"""
    try:
        # Secure the filename
        filename = secure_filename(filename)
        return send_from_directory(str(IMAGE_DIR), filename)
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        return jsonify({'error': 'Image not found'}), 404

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Additional imports for development
    from werkzeug.debug import DebuggedApplication

    # Set development configurations
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    if app.debug:
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
