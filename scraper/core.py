# scraper/core.py

import os
import logging
import time
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import quote
from bs4 import BeautifulSoup

from selenium import webdriver
from sqlalchemy import func

from .selenium_utils import (
    setup_selenium_driver,
    check_for_captcha,
    wait_for_element,
    scroll_page,
    safe_get_url
)
from .data_processors import process_image, save_metadata
from config import JEWELRY_CATEGORIES, MAX_ITEMS_PER_CATEGORY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EbayJewelryScraper:
    def __init__(
        self,
        output_dir: str = "jewelry_dataset",
        image_dir: Optional[str] = None,
        metadata_dir: Optional[str] = None,
        raw_html_dir: Optional[str] = None
    ):
        self.output_dir = output_dir
        self.image_dir = image_dir or os.path.join(output_dir, "images")
        self.metadata_dir = metadata_dir or os.path.join(output_dir, "metadata")
        self.raw_html_dir = raw_html_dir or os.path.join(output_dir, "raw_html")

        # Create necessary directories
        for directory in [self.image_dir, self.metadata_dir, self.raw_html_dir]:
            os.makedirs(directory, exist_ok=True)

        logging.info(f"Initialized scraper with output directory: {self.output_dir}")

    def get_search_url(self, category: str, subcategory: str, page: int = 1) -> str:
        """Generate search URL with proper filters"""
        query = f"{category} {subcategory} jewelry"
        encoded_query = quote(query)
        url = (
            f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
            f"&_pgn={page}&_ipg=48&_dcat=281"
        )
        return url

    def extract_item_data(self, item: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extract data from a single listing"""
        try:
            title_elem = item.select_one('[class*="s-item__title"]')
            price_elem = item.select_one('[class*="s-item__price"], .price')
            link_elem = item.select_one('a[href*="itm"]')
            img_elem = item.select_one('img[src*="i.ebayimg.com"]')

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

            required_fields = ['title', 'price', 'url', 'image_url']
            missing_fields = [field for field in required_fields if not data[field]]

            if missing_fields:
                logging.debug(f"Missing required fields: {missing_fields}")
                return None

            return data

        except Exception as e:
            logging.error(f"Error extracting item data: {e}")
            return None

    def scrape_page(self, driver: webdriver.Chrome, url: str) -> List[Dict[str, str]]:
        """Scrape a single search results page"""
        try:
            # Navigate to URL safely
            if not safe_get_url(driver, url):
                return []

            # Wait for listings to load
            wait_for_element(driver, '[class*="s-item"]', timeout=15)

            # Scroll the page to load dynamic content
            scroll_page(driver)
            time.sleep(2)

            # Check for CAPTCHA
            if check_for_captcha(driver):
                logging.warning("CAPTCHA detected! Waiting for 30 seconds before retrying...")
                time.sleep(30)  # Wait before retrying

            # Save raw HTML
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            html_path = os.path.join(self.raw_html_dir, f"page_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logging.info(f"Saved raw HTML to {html_path}")

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            listings = soup.select('[class*="s-item"]:not([class*="s-item--placeholder"])')

            logging.info(f"Found {len(listings)} potential listings on the page.")

            items = []
            for listing in listings:
                item_data = self.extract_item_data(listing)
                if item_data:
                    items.append(item_data)

            logging.info(f"Extracted {len(items)} valid items from the page.")
            return items

        except Exception as e:
            logging.error(f"Error scraping page {url}: {e}")
            return []

    def scrape_category(
        self,
        category: str,
        subcategory: str,
        max_items: int = 10,
        max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """Scrape items from a specific category"""
        logging.info(f"Starting scrape for Category: {category} | Subcategory: {subcategory}")
        driver = None
        all_items = []
        page = 1

        try:
            driver = setup_selenium_driver()
            if not driver:
                raise Exception("Failed to initialize Selenium driver")

            while len(all_items) < max_items and page <= max_pages:
                url = self.get_search_url(category, subcategory, page)
                logging.info(f"Scraping Page {page}: {url}")
                items = self.scrape_page(driver, url)

                if not items:
                    logging.warning(f"No items found on page {page}. Stopping scrape for this category.")
                    break

                for item in items:
                    if len(all_items) >= max_items:
                        break

                    try:
                        # Define image filename
                        image_filename = f"{category}_{subcategory}_{len(all_items)+1:04d}.jpg"
                        image_path = os.path.join(self.image_dir, image_filename)

                        # Process and save image
                        if process_image(item['image_url'], image_path):
                            item['image_path'] = f"/images/{image_filename}"  # Adjusted for Flask route
                            item['category'] = category
                            item['subcategory'] = subcategory
                            all_items.append(item)
                            logging.info(f"Processed Item {len(all_items)}: {item['title'][:50]}...")

                        time.sleep(random.uniform(0.5, 1.5))

                    except Exception as e:
                        logging.error(f"Error processing item: {e}")
                        continue

                page += 1
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            logging.error(f"Error in scrape_category: {e}")
        finally:
            if driver:
                driver.quit()
                logging.info("Selenium WebDriver closed.")
            if all_items:
                save_metadata(all_items, self.metadata_dir, f"{category}_{subcategory}")

        if not all_items:
            logging.warning(f"No items found for Category: {category} | Subcategory: {subcategory}")

        return all_items
