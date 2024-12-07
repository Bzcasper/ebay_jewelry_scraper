# scraper/core.py

import os
import json
import logging
import time
import random
import re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class EbayJewelryScraper:
    def __init__(self, output_dir: str = "jewelry_dataset"):
        self.output_dir = output_dir
        self.base_url = "https://www.ebay.com"
        self.category_mapping = {
            'necklace': ['Choker', 'Pendant', 'Chain'],
            'pendant': ['Heart', 'Cross', 'Star'],
            'bracelet': ['Tennis', 'Charm', 'Bangle'],
            'ring': ['Engagement', 'Wedding', 'Fashion'],
            'earring': ['Stud', 'Hoop', 'Drop'],
            'wristwatch': ['Analog', 'Digital', 'Smart']
        }
        
        # Ensure output directories exist
        os.makedirs(os.path.join(output_dir, "raw_html"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "metadata"), exist_ok=True)

    def generate_search_url(self, category: str, subcategory: str, page: int = 1) -> str:
        """Generate eBay search URL with filters."""
        params = {
            '_nkw': f"{category} {subcategory} jewelry",
            '_pgn': page,
            '_ipg': 48,  # Items per page
            '_sop': 12,  # Sort by Best Match
            'rt': 'nc',  # No "Buy It Now"
            'LH_BIN': 1  # Buy It Now only
        }
        return f"{self.base_url}/sch/i.html?{urlencode(params)}"

    def extract_price(self, price_elem) -> float:
        """Extract numerical price from price element."""
        if not price_elem:
            return None
            
        try:
            # Handle price ranges (take lower price)
            price_text = price_elem.get_text(strip=True)
            price_text = price_text.replace('$', '').replace(',', '')
            
            if 'to' in price_text.lower():
                price_text = price_text.split('to')[0]
            
            # Extract first valid price number
            matches = re.findall(r'\d+\.?\d*', price_text)
            if matches:
                return float(matches[0])
        except Exception as e:
            logging.error(f"Price extraction error: {e}")
        return None

    def extract_product_data(self, item_elem) -> dict:
        """Extract all product data from a listing element."""
        try:
            # Title with multiple selector fallbacks
            title_elem = item_elem.select_one('.s-item__title, .lvtitle, h3[class*="title"]')
            if not title_elem or 'Shop on eBay' in title_elem.text:
                return None

            # Price with multiple formats
            price_elem = item_elem.select_one('.s-item__price, .lvprice, span[class*="price"]')
            price = self.extract_price(price_elem)
            if not price:
                return None

            # Image URL handling both standard and lazy-loaded images
            img_elem = item_elem.select_one('.s-item__image-img, img[src*="i.ebayimg.com"]')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src')
                if 'ir.ebaystatic.com' in image_url:  # Skip placeholder images
                    return None

            # Product URL
            link_elem = item_elem.select_one('a.s-item__link, .lvtitle a')
            if not link_elem or not link_elem.get('href'):
                return None

            # Additional details
            condition_elem = item_elem.select_one('.s-item__condition, .condText')
            seller_elem = item_elem.select_one('.s-item__seller-info-text, .sellerInfo')
            location_elem = item_elem.select_one('.s-item__location, .lvlocation')
            shipping_elem = item_elem.select_one('.s-item__shipping, .ship')
            
            # Sales data
            sold_count_elem = item_elem.select_one('.s-item__quantitySold, .hotness-signal')
            watches_elem = item_elem.select_one('.s-item__watchCount, .watchcount')

            # Build complete product data
            product_data = {
                'title': title_elem.get_text(strip=True),
                'price': price,
                'image_url': image_url,
                'url': link_elem['href'],
                'condition': condition_elem.get_text(strip=True) if condition_elem else None,
                'seller': seller_elem.get_text(strip=True) if seller_elem else None,
                'location': location_elem.get_text(strip=True) if location_elem else None,
                'shipping': shipping_elem.get_text(strip=True) if shipping_elem else None,
                'sold_count': self._extract_number(sold_count_elem.get_text()) if sold_count_elem else 0,
                'watch_count': self._extract_number(watches_elem.get_text()) if watches_elem else 0
            }

            return product_data

        except Exception as e:
            logging.error(f"Error extracting product data: {e}")
            return None

    def _extract_number(self, text: str) -> int:
        """Extract first number from text string."""
        if not text:
            return 0
        matches = re.findall(r'\d+', text)
        return int(matches[0]) if matches else 0

    def scrape_listing_page(self, driver, url: str) -> list:
        """Scrape a single page of product listings."""
        products = []
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # Load page and wait for products
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".s-item"))
                )
                
                # Scroll to load lazy images
                self._scroll_page(driver)
                time.sleep(2)  # Wait for dynamic content

                # Parse page content
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Find all product listings
                listings = soup.select('.s-item:not(.s-item--placeholder)')
                
                # Extract data from each listing
                for item in listings:
                    if product_data := self.extract_product_data(item):
                        products.append(product_data)

                return products

            except TimeoutException:
                retry_count += 1
                logging.warning(f"Timeout on {url}, attempt {retry_count} of {max_retries}")
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logging.error(f"Error scraping listing page: {e}")
                return products

        return products

    def _scroll_page(self, driver):
        """Scroll page to load all content."""
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def scrape_category(self, category: str, subcategory: str, max_pages: int = 5) -> list:
        """Scrape products from a category/subcategory combination."""
        all_products = []
        driver = None

        try:
            driver = self._setup_driver()
            
            for page in range(1, max_pages + 1):
                url = self.generate_search_url(category, subcategory, page)
                logging.info(f"Scraping {category}/{subcategory} - Page {page}")
                
                products = self.scrape_listing_page(driver, url)
                if not products:
                    break
                    
                all_products.extend(products)
                
                # Save progress
                self._save_results(all_products, category, subcategory)
                
                # Random delay between pages
                time.sleep(random.uniform(2, 5))

        except Exception as e:
            logging.error(f"Error scraping category {category}/{subcategory}: {e}")
        finally:
            if driver:
                driver.quit()

        return all_products

    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver with proper options."""
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        return webdriver.Chrome(options=options)

    def _save_results(self, products: list, category: str, subcategory: str):
        """Save scraped products to JSON file."""
        if not products:
            return

        filename = f"{category}_{subcategory}_{int(time.time())}.json"
        filepath = os.path.join(self.output_dir, "metadata", filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2)

        logging.info(f"Saved {len(products)} products to {filepath}")