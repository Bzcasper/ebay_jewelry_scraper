# scraper/product_collector.py

import logging
import re
from typing import Dict, Optional, List
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class ProductDataCollector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define selectors based on eBay's structure
        self.selectors = {
            'product_container': [
                '.s-item__wrapper',
                '.srp-results .s-item',
                '.gvprices'
            ],
            'title': [
                '.s-item__title',
                'h3.lvtitle',
                '.g-title'
            ],
            'price': [
                '.s-item__price',
                '.g-price',
                'span[itemprop="price"]',
                '.lvprice .bold'
            ],
            'shipping': [
                '.s-item__shipping',
                '.s-item__logisticsCost',
                '.ship .fee',
                '.g-shipping'
            ],
            'condition': [
                '.s-item__condition',
                '.condText',
                '.g-condition'
            ],
            'image': [
                '.s-item__image-img',
                'img[src*="i.ebayimg.com"]',
                '.g-image img'
            ],
            'link': [
                '.s-item__link',
                'a[href*="itm/"]',
                '.g-title a'
            ],
            'seller': [
                '.s-item__seller-info',
                '.mbg-nw',
                '.si-inner'
            ],
            'reviews': [
                '.s-item__seller-info-text',
                '.arrow span',
                '.g-rating'
            ],
            'watchers': [
                '.s-item__watchCount',
                '.vi-watchcount',
                '.g-watchers'
            ],
            'sold': [
                '.s-item__quantitySold',
                '.vi-qtyS',
                '.g-sold'
            ]
        }
        
        # Keywords to identify jewelry types
        self.jewelry_keywords = {
            'necklace': ['necklace', 'choker', 'collar', 'chain', 'pendant'],
            'pendant': ['pendant', 'charm', 'locket'],
            'bracelet': ['bracelet', 'bangle', 'cuff', 'tennis bracelet'],
            'ring': ['ring', 'band', 'engagement', 'wedding ring'],
            'earring': ['earring', 'stud', 'hoop', 'drop earring'],
            'wristwatch': ['watch', 'timepiece', 'wristwatch']
        }

    def extract_product_details(self, item_elem: Tag) -> Optional[Dict]:
        """Extract all available product details from a listing element."""
        try:
            # Get base product data
            title = self._extract_title(item_elem)
            if not title or 'Shop on eBay' in title:
                return None
                
            # Get main product URL
            product_url = self._extract_link(item_elem)
            if not product_url:
                return None

            # Extract price information
            price_info = self._extract_price_info(item_elem)
            if not price_info:
                return None

            # Get primary product image
            image_url = self._extract_image_url(item_elem)
            if not image_url or 'ir.ebaystatic.com' in image_url:
                return None

            # Get seller information
            seller_info = self._extract_seller_info(item_elem)
            
            # Build product data dictionary
            product_data = {
                'title': title,
                'url': product_url,
                'price': price_info['price'],
                'price_range': price_info.get('price_range'),
                'original_price': price_info.get('original_price'),
                'image_url': image_url,
                'condition': self._extract_with_selectors(item_elem, self.selectors['condition']),
                'shipping': self._extract_shipping(item_elem),
                'seller': seller_info,
                'watchers': self._extract_number(self._extract_with_selectors(item_elem, self.selectors['watchers'])),
                'sold_count': self._extract_number(self._extract_with_selectors(item_elem, self.selectors['sold'])),
                'category': self._determine_jewelry_type(title)
            }

            # Additional gallery images if available
            gallery_images = self._extract_gallery_images(item_elem)
            if gallery_images:
                product_data['gallery_images'] = gallery_images

            return product_data

        except Exception as e:
            self.logger.error(f"Error extracting product details: {e}")
            return None

    def _extract_title(self, item_elem: Tag) -> Optional[str]:
        """Extract and clean product title."""
        title = self._extract_with_selectors(item_elem, self.selectors['title'])
        if title:
            # Remove "New Listing" and similar prefixes
            title = re.sub(r'^New Listing|^NEW LISTING|^New', '', title).strip()
            # Remove multiple spaces
            title = ' '.join(title.split())
            return title
        return None

    def _extract_price_info(self, item_elem: Tag) -> Optional[Dict]:
        """Extract complete price information including ranges and original prices."""
        price_elem = self._find_element(item_elem, self.selectors['price'])
        if not price_elem:
            return None

        price_text = price_elem.get_text(strip=True)
        
        try:
            price_info = {}
            
            # Handle price ranges (e.g., "$10.99 to $24.99")
            if ' to ' in price_text:
                low, high = price_text.split(' to ')
                price_info['price'] = self._extract_price_value(low)
                price_info['price_range'] = {
                    'low': self._extract_price_value(low),
                    'high': self._extract_price_value(high)
                }
            else:
                price_info['price'] = self._extract_price_value(price_text)

            # Check for original/struck-through price
            original_price_elem = item_elem.select_one('.s-item__original-price, .g-original')
            if original_price_elem:
                price_info['original_price'] = self._extract_price_value(
                    original_price_elem.get_text(strip=True)
                )

            return price_info if price_info.get('price') else None

        except Exception as e:
            self.logger.error(f"Error extracting price info: {e}")
            return None

    def _extract_price_value(self, price_text: str) -> Optional[float]:
        """Extract numerical price from text."""
        try:
            # Remove currency symbols and commas
            price_text = price_text.replace('$', '').replace(',', '')
            # Extract first valid price number
            matches = re.findall(r'\d+\.?\d*', price_text)
            return float(matches[0]) if matches else None
        except Exception:
            return None

    def _extract_image_url(self, item_elem: Tag) -> Optional[str]:
        """Extract primary product image URL."""
        img_elem = self._find_element(item_elem, self.selectors['image'])
        if not img_elem:
            return None
            
        # Check for lazy-loaded images
        image_url = img_elem.get('data-src') or img_elem.get('src')
        
        # Convert thumbnail URLs to full-size images
        if image_url and 's-l64' in image_url:
            image_url = image_url.replace('s-l64', 's-l1600')
            
        return image_url

    def _extract_gallery_images(self, item_elem: Tag) -> List[str]:
        """Extract additional product gallery images if available."""
        gallery_images = []
        gallery_elems = item_elem.select('.pic .img[src*="i.ebayimg.com"], .s-item__image-gallery img')
        
        for img in gallery_elems:
            image_url = img.get('data-src') or img.get('src')
            if image_url and image_url not in gallery_images:
                # Convert to full-size image URL
                image_url = re.sub(r's-l\d+', 's-l1600', image_url)
                gallery_images.append(image_url)
                
        return gallery_images

    def _extract_shipping(self, item_elem: Tag) -> Dict:
        """Extract detailed shipping information."""
        shipping_info = {
            'cost': None,
            'method': None,
            'location': None,
            'is_free': False
        }

        shipping_elem = self._find_element(item_elem, self.selectors['shipping'])
        if shipping_elem:
            text = shipping_elem.get_text(strip=True).lower()
            
            # Check for free shipping
            if 'free' in text:
                shipping_info['is_free'] = True
                shipping_info['cost'] = 0.0
            else:
                # Extract shipping cost
                cost_match = re.search(r'\$(\d+\.?\d*)', text)
                if cost_match:
                    shipping_info['cost'] = float(cost_match.group(1))

            # Extract shipping method
            if 'expedited' in text:
                shipping_info['method'] = 'Expedited'
            elif 'economy' in text:
                shipping_info['method'] = 'Economy'
            elif 'standard' in text:
                shipping_info['method'] = 'Standard'

        # Extract location
        location_elem = item_elem.select_one('.s-item__location, .location')
        if location_elem:
            shipping_info['location'] = location_elem.get_text(strip=True)

        return shipping_info

    def _extract_seller_info(self, item_elem: Tag) -> Dict:
        """Extract detailed seller information."""
        seller_info = {
            'name': None,
            'feedback_score': None,
            'positive_feedback': None,
            'top_rated': False
        }

        seller_elem = self._find_element(item_elem, self.selectors['seller'])
        if seller_elem:
            # Extract seller name
            name_elem = seller_elem.select_one('.mbg-nw')
            if name_elem:
                seller_info['name'] = name_elem.get_text(strip=True)

            # Extract feedback score
            feedback_elem = seller_elem.select_one('.mbg-l')
            if feedback_elem:
                feedback_text = feedback_elem.get_text(strip=True)
                score_match = re.search(r'\d+', feedback_text)
                if score_match:
                    seller_info['feedback_score'] = int(score_match.group())

            # Check for top-rated status
            top_rated_elem = item_elem.select_one('.s-item__etrs-icon, .top-rated')
            seller_info['top_rated'] = bool(top_rated_elem)

            # Extract positive feedback percentage
            positive_elem = seller_elem.select_one('.positive-feedback')
            if positive_elem:
                percentage_match = re.search(r'(\d+\.?\d*)%', positive_elem.get_text())
                if percentage_match:
                    seller_info['positive_feedback'] = float(percentage_match.group(1))

        return seller_info

    def _determine_jewelry_type(self, title: str) -> Dict[str, str]:
        """Determine jewelry type and subcategory from title."""
        title_lower = title.lower()
        
        for category, keywords in self.jewelry_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                # Determine subcategory
                subcategory = self._determine_subcategory(title_lower, category)
                return {
                    'main_category': category,
                    'subcategory': subcategory
                }
        
        return {
            'main_category': 'other',
            'subcategory': 'unknown'
        }

    def _determine_subcategory(self, title: str, main_category: str) -> str:
        """Determine specific subcategory based on title and main category."""
        subcategories = {
            'necklace': {
                'choker': ['choker'],
                'pendant': ['pendant'],
                'chain': ['chain', 'rope', 'box chain', 'cuban'],
                'statement': ['statement', 'bib', 'collar']
            },
            'ring': {
                'engagement': ['engagement', 'bridal', 'wedding'],
                'fashion': ['fashion', 'statement', 'cocktail'],
                'band': ['band', 'eternity', 'stackable']
            },
            'earring': {
                'stud': ['stud'],
                'hoop': ['hoop'],
                'drop': ['drop', 'dangle', 'chandelier'],
                'cluster': ['cluster']
            }
        }

        if main_category in subcategories:
            for subcategory, keywords in subcategories[main_category].items():
                if any(keyword in title for keyword in keywords):
                    return subcategory
                    
        return 'other'

    def _extract_with_selectors(self, elem: Tag, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors and return first successful result."""
        for selector in selectors:
            found_elem = elem.select_one(selector)
            if found_elem:
                return found_elem.get_text(strip=True)
        return None

    def _find_element(self, elem: Tag, selectors: List[str]) -> Optional[Tag]:
        """Find first element matching any of the provided selectors."""
        for selector in selectors:
            found_elem = elem.select_one(selector)
            if found_elem:
                return found_elem
        return None

    def _extract_number(self, text: Optional[str]) -> Optional[int]:
        """Extract first number from text string."""
        if not text:
            return None
        matches = re.findall(r'\d+', text)
        return int(matches[0]) if matches else None

    def wait_for_products(self, driver, timeout: int = 10) -> bool:
        """Wait for product listings to load on page."""
        try:
            # Wait for any of the product container selectors
            for selector in self.selectors['product_container']:
                try:
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    return True
                except TimeoutException:
                    continue
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for products: {e}")
            return False