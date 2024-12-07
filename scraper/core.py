# scraper/core.py
import os
import json
import logging
import time
import random
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from .selenium_utils import setup_selenium_driver, safe_get_url, check_for_captcha, wait_for_element, scroll_page
from .data_processors import DatasetProcessor
from typing import List, Dict, Optional  # Added imports

class EbayJewelryScraper:
    def __init__(self, output_dir: str = "jewelry_dataset", proxies: Optional[List[str]] = None, user_agents: Optional[List[str]] = None):
        """
        Initialize the EbayJewelryScraper with optional proxies and user-agents.
        
        Args:
            output_dir (str): Base directory for output data.
            proxies (Optional[List[str]]): List of proxy URLs.
            user_agents (Optional[List[str]]): List of user-agent strings.
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
        encoded_query = quote(query)
        url = (f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
               f"&_pgn={page}&_ipg=48&_dcat=281")  # Adjust _dcat as needed for specific categories
        return url

    def rotate_proxy_and_user_agent(self, driver):
        """
        Rotate proxies and user-agent strings for each session to minimize blocking.
        
        Args:
            driver: Selenium WebDriver instance.
        """
        if self.proxies:
            proxy = self.proxies[self.proxy_index % len(self.proxies)]
            self.proxy_index += 1
            # Configure proxy for Selenium WebDriver
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': {'Proxy-Authorization': proxy}})
            logging.info(f"Using proxy: {proxy}")
        
        if self.user_agents:
            user_agent = self.user_agents[self.user_agent_index % len(self.user_agents)]
            self.user_agent_index += 1
            # Set user-agent for Selenium WebDriver
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            logging.info(f"Using User-Agent: {user_agent}")

    def extract_price(self, price_text: str) -> Optional[float]:
        """
        Extract numerical price from text.
        
        Args:
            price_text (str): Text containing the price.
        
        Returns:
            Optional[float]: Extracted price or None if not found.
        """
        if not price_text:
            return None
        match = re.search(r'[\d,.]+', price_text)
        return float(match.group(0).replace(',', '')) if match else None
    
    def extract_item_data(self, item: BeautifulSoup) -> Optional[Dict]:
        """
        Extract detailed item data from a listing element.
        
        Args:
            item (BeautifulSoup): BeautifulSoup object representing a single listing.
        
        Returns:
            Optional[Dict]: Dictionary containing extracted item data or None if extraction fails.
        """
        try:
            # Selectors for different elements
            title_elem = item.select_one('[class*="s-item__title"]')
            price_elem = item.select_one('[class*="s-item__price"], .price')
            link_elem = item.select_one('a[href*="itm"]')
            img_elem = item.select_one('img[src*="i.ebayimg.com"]')
            condition_elem = item.select_one('[class*="s-item__condition"]')
            subtitle_elem = item.select_one('[class*="s-item__subtitle"]')
            
            # Verify required elements
            if not all([title_elem, price_elem, link_elem, img_elem]):
                return None
            
            # Extract and structure data
            data = {
                'title': title_elem.get_text(strip=True),
                'price': self.extract_price(price_elem.get_text(strip=True)),
                'url': link_elem['href'],
                'image_url': img_elem['src'],
                'condition': condition_elem.get_text(strip=True) if condition_elem else None,
                'subtitle': subtitle_elem.get_text(strip=True) if subtitle_elem else None,
            }
            
            # Get additional details from product page
            if data['url']:
                details = self.get_product_details(data['url'])
                data.update(details)
            
            return data
            
        except Exception as e:
            logging.error(f"Error extracting item data: {e}")
            return None

    def get_product_details(self, url: str) -> Dict:
        """
        Get additional details from the product page.
        
        Args:
            url (str): URL of the product page.
        
        Returns:
            Dict: Dictionary containing additional details like description, specifications, and seller info.
        """
        details = {
            'description': '',
            'specifications': {},
            'seller_info': {}
        }
        driver = None
        try:
            driver = setup_selenium_driver()
            self.rotate_proxy_and_user_agent(driver)
            driver.get(url)
            time.sleep(2)  # Wait for page to load
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Get product description
            desc_elem = soup.select_one('#desc_wrapper')
            if desc_elem:
                details['description'] = desc_elem.get_text(separator=' ', strip=True)
            
            # Get specifications
            spec_table = soup.select('div.itemAttr table tr')
            for row in spec_table:
                label = row.select_one('td.attrLabel')
                value = row.select_one('td.attrValue')
                if label and value:
                    details['specifications'][label.get_text(strip=True)] = value.get_text(strip=True)
            
            # Get seller information
            seller_elem = soup.select_one('#RightSummaryPanel .mbg .mbg-l a')
            if seller_elem:
                details['seller_info']['name'] = seller_elem.get_text(strip=True)
                details['seller_info']['url'] = seller_elem['href']
            
        except WebDriverException as e:
            logging.error(f"WebDriver exception while getting product details: {e}")
        except Exception as e:
            logging.error(f"Error getting product details: {e}")
        finally:
            if driver:
                driver.quit()
        
        return details

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
            driver = setup_selenium_driver()
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
                        # Process and save image is already handled in process_item
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
