# app.py
from flask import Flask, render_template, jsonify, request
import logging
from scraper.core import EbayJewelryScraper
import threading
import queue

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global variables for tracking progress
scraping_progress = {
    'status': 'idle',
    'current_category': None,
    'items_found': 0,
    'error': None
}

# Queue for background tasks
task_queue = queue.Queue()

def run_scraper(category, subcategory):
    global scraping_progress
    try:
        scraping_progress['status'] = 'running'
        scraping_progress['current_category'] = f"{category} - {subcategory}"
        scraping_progress['items_found'] = 0
        scraping_progress['error'] = None

        scraper = EbayJewelryScraper()
        items = scraper.scrape_category(category, subcategory)
        
        scraping_progress['items_found'] = len(items)
        scraping_progress['status'] = 'completed'

    except Exception as e:
        logging.error(f"Scraping error: {str(e)}")
        scraping_progress['status'] = 'error'
        scraping_progress['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    data = request.get_json()
    category = data.get('category', 'Rings')
    subcategory = data.get('subcategory', 'Engagement')
    
    # Start scraping in background thread
    thread = threading.Thread(
        target=run_scraper,
        args=(category, subcategory)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/progress')
def get_progress():
    return jsonify(scraping_progress)

if __name__ == '__main__':
    app.run(debug=True)