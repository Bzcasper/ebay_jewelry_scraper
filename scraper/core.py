# scraper/core.py
import os
import json
import logging
import time
import random
from urllib.parse import quote
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .selenium_utils import setup_selenium_driver, safe_get_url, check_for_captcha, wait_for_element, scroll_page
from .data_processors import process_image, save_metadata

class EbayJewelryScraper:
    def __init__(self, output_dir="jewelry_dataset"):
        self.output_dir = output_dir
        self.image_dir = os.path.join(output_dir, "images")
        self.metadata_dir = os.path.join(output_dir, "metadata")
        self.raw_html_dir = os.path.join(output_dir, "raw_html")
        
        # Create necessary directories
        for directory in [self.image_dir, self.metadata_dir, self.raw_html_dir]:
            os.makedirs(directory, exist_ok=True)
            
        logging.info(f"Initialized scraper with output directory: {output_dir}")

    def get_search_url(self, category, subcategory, page=1):
        """Generate search URL with proper filters"""
        query = f"{category} {subcategory} jewelry"
        encoded_query = quote(query)
        url = (f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
               f"&_pgn={page}&_ipg=48&_dcat=281")
        return url

    def extract_item_data(self, item):
        """Extract data from a single listing with improved selectors"""
        try:
            # Updated selectors to match current eBay structure
            title_elem = item.select_one('[class*="s-item__title"]')
            price_elem = item.select_one('[class*="s-item__price"], .price')
            link_elem = item.select_one('a[href*="itm"]')
            img_elem = item.select_one('img[src*="i.ebayimg.com"]')
            
            # Debug logging
            logging.debug(f"Raw title element: {title_elem}")
            logging.debug(f"Raw price element: {price_elem}")
            logging.debug(f"Raw link element: {link_elem}")
            logging.debug(f"Raw image element: {img_elem}")
            
            # Extract and clean data
            data = {
                'title': title_elem.get_text(strip=True) if title_elem else None,
                'price': price_elem.get_text(strip=True).replace('US $', '').strip() if price_elem else None,
                'url': link_elem['href'] if link_elem and 'href' in link_elem.attrs else None,
                'image_url': img_elem['src'] if img_elem and 'src' in img_elem.attrs else None
            }
            
            # Additional metadata
            condition_elem = item.select_one('[class*="condition"]')
            shipping_elem = item.select_one('[class*="shipping"]')
            seller_elem = item.select_one('[class*="seller"]')
            location_elem = item.select_one('[class*="location"]')
            
            if condition_elem:
                data['condition'] = condition_elem.get_text(strip=True)
            if shipping_elem:
                data['shipping'] = shipping_elem.get_text(strip=True)
            if seller_elem:
                data['seller'] = seller_elem.get_text(strip=True)
            if location_elem:
                data['location'] = location_elem.get_text(strip=True)
                
            # Validate required fields
            required_fields = ['title', 'price', 'url', 'image_url']
            missing_fields = [field for field in required_fields if not data[field]]
            
            if missing_fields:
                logging.debug(f"Missing required fields: {missing_fields}")
                return None
                
            return data
                
        except Exception as e:
            logging.error(f"Error extracting item data: {str(e)}")
            return None

    def scrape_page(self, driver, url):
        """Scrape a single search results page with improved handling"""
        try:
            if not safe_get_url(driver, url):
                return []

            # Wait for product grid to load
            wait_for_element(driver, '[class*="s-item"]', timeout=15)
            
            # Handle dynamic content
            scroll_page(driver)
            time.sleep(2)
            
            # Check for CAPTCHA
            if check_for_captcha(driver):
                logging.warning("CAPTCHA detected!")
                time.sleep(30)  # Wait for manual solving
                
            # Save raw HTML for debugging
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            html_path = os.path.join(self.raw_html_dir, f"page_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            # Parse updated page content
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            listings = soup.select('[class*="s-item"]:not([class*="s-item--placeholder"])')
            
            logging.info(f"Found {len(listings)} potential listings")
            
            items = []
            for listing in listings:
                item_data = self.extract_item_data(listing)
                if item_data:
                    items.append(item_data)
                    
            logging.info(f"Successfully extracted {len(items)} valid items")
            return items

        except Exception as e:
            logging.error(f"Error scraping page {url}: {str(e)}")
            return []

    def scrape_category(self, category, subcategory, max_items=10, max_pages=5):
        """Scrape items from a specific category with improved error handling"""
        logging.info(f"Starting scrape for {category} - {subcategory}")
        driver = None
        all_items = []
        page = 1
        
        try:
            driver = setup_selenium_driver()
            
            while len(all_items) < max_items and page <= max_pages:
                url = self.get_search_url(category, subcategory, page)
                items = self.scrape_page(driver, url)
                
                if not items:
                    logging.warning(f"No items found on page {page}")
                    break
                    
                for item in items:
                    if len(all_items) >= max_items:
                        break
                        
                    try:
                        # Process and save image
                        image_filename = f"{category}_{subcategory}_{len(all_items):04d}.jpg"
                        image_path = os.path.join(self.image_dir, image_filename)
                        
                        if process_image(item['image_url'], image_path):
                            item['image_path'] = image_path
                            item['category'] = category
                            item['subcategory'] = subcategory
                            all_items.append(item)
                            logging.info(f"Processed item {len(all_items)}: {item['title'][:50]}...")
                        
                        time.sleep(random.uniform(0.5, 1.5))
                        
                    except Exception as e:
                        logging.error(f"Error processing item: {str(e)}")
                        continue

                page += 1
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            logging.error(f"Error in scrape_category: {str(e)}")
        finally:
            if driver:
                driver.quit()
            if all_items:
                save_metadata(all_items, self.metadata_dir, f"{category}_{subcategory}")

        if not all_items:
            logging.warning(f"No items found for {category} - {subcategory}")
            
        return all_items