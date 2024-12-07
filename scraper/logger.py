# scraper/logger.py
import logging
from google.cloud import logging as cloud_logging
import os

def setup_logging():
    # Initialize standard logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize Google Cloud Logging if credentials are provided
    if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        client = cloud_logging.Client()
        client.setup_logging()
        logging.info("Google Cloud Logging initialized.")
    else:
        logging.warning("Google Cloud Credentials not found. Using standard logging.")
