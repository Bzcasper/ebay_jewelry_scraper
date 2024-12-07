# scraper/core.py

import logging
import os
import time
import random
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

from .selenium_utils import setup_selenium_driver, safe_get_url, check_for_captcha, wait_for_element, scroll_page
from .data_processors import DatasetProcessor

class EbayJewelryScraper:
    def __init__(self, output_dir: str = "jewelry_dataset", proxies: List[str] = None, user_agents: List[str] = None):
        """
        Initialize the EbayJewelryScraper with optional proxies and user-agents.
        
        Args:
            output_dir (str): Base directory for output data.
            proxies (List[str], optional): List of proxy server addresses.
            user_agents (List[str], optional): List of user-agent strings.
        """
        self.output_dir = output_dir
        self.processor = DatasetProcessor(base_dir=output_dir)
        self.proxies = proxies if proxies else []
        self.user_agents = user_agents if user_agents else []
        self.proxy_index = 0
        self.user_agent_index = 0
        
    def get_search_url(self, category: str, subcategory: str, page: int = 1) -> str:
        """
        Generate search URL with proper filters for a given category and subcategory.
        
        Args:
            category (str): Main category name.
            subcategory (str): Subcategory name.
            page (int): Page number for pagination.
        
        Returns:
            str: Constructed search URL.
        """
        query = f"{category} {subcategory} jewelry"
        encoded_query = query.replace(' ', '+')  # Simple encoding
        url = (f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
               f"&_pgn={page}&_ipg=48&_dcat=281")  # Adjust _dcat as needed for specific categories
        return url

    def rotate_proxy_and_user_agent(self, driver: webdriver.Chrome):
        """
        Rotate proxies and user-agent strings for each session to minimize blocking.
        
        Args:
            driver (webdriver.Chrome): Selenium WebDriver instance.
        """
        if self.proxies:
            proxy = self.proxies[self.proxy_index % len(self.proxies)]
            self.proxy_index += 1
            # Configure proxy for Selenium WebDriver
            # Note: Proper proxy setup may require more configuration
            # Here, we'll set it via Chrome options
            driver.set_window_size(1920, 1080)
            logging.info(f"Using proxy: {proxy}")
        
        if self.user_agents:
            user_agent = self.user_agents[self.user_agent_index % len(self.user_agents)]
            self.user_agent_index += 1
            # Set user-agent for Selenium WebDriver
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            logging.info(f"Using User-Agent: {user_agent}")

    def extract_price(self, price_text: str) -> float:
        """
        Extract numerical price from text.
        
        Args:
            price_text (str): Text containing the price.
        
        Returns:
            float: Extracted price or 0.0 if not found.
        """
        if not price_text:
            return 0.0
        try:
            # Remove currency symbols and convert to float
            price = ''.join(c for c in price_text if c.isdigit() or c == '.')
            return float(price) if price else 0.0
        except ValueError:
            logging.warning(f"Unable to extract price from text: {price_text}")
            return 0.0
    
    def extract_item_data(self, item: BeautifulSoup) -> Dict:
        """
        Extract detailed item data from a listing element.
        
        Args:
            item (BeautifulSoup): BeautifulSoup object representing a single listing.
        
        Returns:
            Dict: Dictionary containing extracted item data.
        """
        try:
            # Selectors for different elements
            title_elem = item.select_one('[class*="s-item__title"]')
            price_elem = item.select_one('[class*="s-item__price"]')
            link_elem = item.select_one('a[href*="itm"]')
            img_elem = item.select_one('img[src*="i.ebayimg.com"]')
            condition_elem = item.select_one('[class*="s-item__condition"]')
            
            # Verify required elements
            if not all([title_elem, price_elem, link_elem, img_elem]):
                return {}
            
            # Extract and structure data
            data = {
                'title': title_elem.get_text(strip=True),
                'price': self.extract_price(price_elem.get_text(strip=True)),
                'url': link_elem['href'],
                'image_url': img_elem['src'],
                'condition': condition_elem.get_text(strip=True) if condition_elem else 'Unknown',
            }
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting item data: {e}")
            return {}
    
    def scrape_page(self, driver: webdriver.Chrome, url: str) -> List[Dict]:
        """
        Scrape a single search results page with improved handling.
        
        Args:
            driver (webdriver.Chrome): Selenium WebDriver instance.
            url (str): URL of the search results page.
        
        Returns:
            List[Dict]: List of extracted item data dictionaries.
        """
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
                logging.warning("CAPTCHA detected! Waiting for manual resolution...")
                time.sleep(30)  # Wait time can be adjusted or integrated with CAPTCHA solving services
            
            # Save raw HTML for debugging
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            html_path = os.path.join(self.output_dir, "raw_html", f"page_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            # Parse updated page content
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            listings = soup.select('[class*="s-item"]:not([class*="s-item--placeholder"])')
            
            logging.info(f"Found {len(listings)} potential listings on page.")
            
            items = []
            for listing in listings:
                item_data = self.extract_item_data(listing)
                if item_data:
                    items.append(item_data)
                    
            logging.info(f"Successfully extracted {len(items)} valid items from page.")
            return items

        except Exception as e:
            logging.error(f"Error scraping page {url}: {e}")
            return []

    def scrape_category(self, category: str, subcategory: str, max_items: int = 100, max_pages: int = 5) -> List[Dict]:
        """
        Scrape items from a specific category and subcategory with improved error handling.
        
        Args:
            category (str): Main category name.
            subcategory (str): Subcategory name.
            max_items (int): Maximum number of items to scrape.
            max_pages (int): Maximum number of pages to scrape.
        
        Returns:
            List[Dict]: List of scraped item data dictionaries.
        """
        logging.info(f"Starting scrape for Category: '{category}' | Subcategory: '{subcategory}'")
        driver = None
        all_items = []
        page = 1
        
        try:
            driver = setup_selenium_driver(proxies=self.proxies, user_agent=random.choice(self.user_agents))
            self.rotate_proxy_and_user_agent(driver)
            
            while len(all_items) < max_items and page <= max_pages:
                url = self.get_search_url(category, subcategory, page)
                logging.info(f"Scraping URL: {url}")
                items = self.scrape_page(driver, url)
                
                if not items:
                    logging.warning(f"No items found on page {page}. Ending scrape for this subcategory.")
                    break
                    
                for item in items:
                    if len(all_items) >= max_items:
                        break
                        
                    try:
                        all_items.append(item)
                        logging.info(f"Processed item {len(all_items)}: {item['title'][:50]}...")
                        
                        time.sleep(random.uniform(0.5, 1.5))  # Random delay to mimic human behavior
                        
                    except Exception as e:
                        logging.error(f"Error processing item: {e}")
                        continue

                page += 1
                time.sleep(random.uniform(2, 4))  # Random delay between pages

        except Exception as e:
            logging.error(f"Error in scrape_category: {e}")
        finally:
            if driver:
                driver.quit()
        
        if all_items:
            self.processor.create_dataset(all_items)
            logging.info(f"Completed scrape for Category: '{category}' | Subcategory: '{subcategory}' | Items Scraped: {len(all_items)}")
        else:
            logging.warning(f"No items scraped for Category: '{category}' | Subcategory: '{subcategory}'")
            
        return all_items
