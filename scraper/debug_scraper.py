# debug_scraper.py
import logging
from scraper.core import EbayJewelryScraper

if __name__ == '__main__':
    # Configure detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler('debug.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize scraper with test configuration
    scraper = EbayJewelryScraper(output_dir="test_dataset")
    
    # Test categories
    test_categories = [
        ('Rings', 'Engagement'),
        ('Necklaces', 'Chains'),
        ('Bracelets', 'Tennis')
    ]
    
    # Run test scrapes
    for category, subcategory in test_categories:
        logging.info(f"Testing scrape for {category} - {subcategory}")
        try:
            items = scraper.scrape_category(
                category,
                subcategory,
                max_items=5,
                max_pages=2
            )
            logging.info(f"Found {len(items)} items")
        except Exception as e:
            logging.error(f"Test failed: {str(e)}")
