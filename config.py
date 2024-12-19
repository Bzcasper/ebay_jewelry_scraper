# config.py
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Data directories
DATA_DIR = BASE_DIR / 'data'
IMAGE_DIR = DATA_DIR / 'images'
METADATA_DIR = DATA_DIR / 'metadata'
RAW_HTML_DIR = DATA_DIR / 'raw_html'
LOG_DIR = BASE_DIR / 'logs'

# Ensure directories exist
for directory in [IMAGE_DIR, METADATA_DIR, RAW_HTML_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = f"sqlite:///{DATA_DIR}/jewelry.db"

# Scraping settings
MAX_ITEMS_PER_CATEGORY = 100
MAX_RETRIES = 3
RETRY_DELAY = 2
PAGE_LOAD_TIMEOUT = 30
SCROLL_PAUSE_TIME = 1

# Image settings
MAX_IMAGE_SIZE = (800, 800)
IMAGE_QUALITY = 85

# Browser settings
WINDOW_SIZE = (1920, 1080)
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

# Categories
JEWELRY_CATEGORIES = {
    'Rings': ['Engagement', 'Wedding', 'Fashion'],
    'Necklaces': ['Pendants', 'Chains', 'Chokers'],
    'Bracelets': ['Tennis', 'Bangles', 'Charm'],
    'Earrings': ['Studs', 'Hoops', 'Drops']
}

# Flask settings
FLASK_DEBUG = True
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
