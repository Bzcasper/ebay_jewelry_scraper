# scraper/selenium_utils.py

import os
import json
import time
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

class SeleniumManager:
    def __init__(self, config: Dict, proxy_list: Optional[List[str]] = None):
        self.config = config
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0
        self.logger = logging.getLogger(__name__)
        
        # Setup cookie and user-agent management
        self.cookies_dir = Path("data/cookies")
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/91.0.864.59"
        ]

    def create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver instance."""
        options = self._configure_chrome_options()
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Set page load timeout
            driver.set_page_load_timeout(self.config['selenium_config']['page_load_timeout'])
            
            # Set window size
            driver.set_window_size(*self.config['selenium_config']['window_size'])
            
            # Add stealth settings
            self._add_stealth_settings(driver)
            
            return driver
            
        except Exception as e:
            self.logger.error(f"Failed to create WebDriver: {e}")
            raise

    def _configure_chrome_options(self) -> Options:
        """Configure Chrome options for WebDriver."""
        options = Options()
        
        # Headless mode if configured
        if self.config['selenium_config']['headless']:
            options.add_argument('--headless')
        
        # Add required arguments
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-notifications')
        
        # Add random user agent
        options.add_argument(f'user-agent={random.choice(self.user_agents)}')
        
        # Add proxy if available
        if self.proxy_list:
            proxy = self._get_next_proxy()
            options.add_argument(f'--proxy-server={proxy}')
        
        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        return options

    def _add_stealth_settings(self, driver: webdriver.Chrome):
        """Add stealth settings to avoid detection."""
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            '''
        })

    def _get_next_proxy(self) -> str:
        """Get next proxy from the list using round-robin."""
        if not self.proxy_list:
            return ''
            
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy

    def safe_get(self, driver: webdriver.Chrome, url: str, max_retries: int = 3) -> bool:
        """Safely navigate to URL with retries."""
        for attempt in range(max_retries):
            try:
                driver.get(url)
                
                # Wait for page load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Check for anti-bot measures
                if self._detect_antibot(driver):
                    self.logger.warning(f"Anti-bot measures detected on {url}")
                    self._handle_antibot(driver)
                
                # Save cookies
                self._save_cookies(driver, url)
                
                return True
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
                    self._rotate_identity(driver)
                    
        return False

    def _detect_antibot(self, driver: webdriver.Chrome) -> bool:
        """Detect common anti-bot measures."""
        indicators = [
            "//div[contains(text(), 'captcha')]",
            "//div[contains(text(), 'verify')]",
            "//div[contains(text(), 'robot')]"
        ]
        
        for indicator in indicators:
            try:
                if driver.find_elements(By.XPATH, indicator):
                    return True
            except:
                continue
                
        return False

    def _handle_antibot(self, driver: webdriver.Chrome):
        """Handle detected anti-bot measures."""
        # Wait and retry with new identity
        time.sleep(random.uniform(10, 20))
        self._rotate_identity(driver)

    def _rotate_identity(self, driver: webdriver.Chrome):
        """Rotate proxy and user agent."""
        if self.proxy_list:
            proxy = self._get_next_proxy()
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {'Proxy-Authorization': proxy}
            })
        
        # Rotate user agent
        new_user_agent = random.choice(self.user_agents)
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": new_user_agent
        })

    def _save_cookies(self, driver: webdriver.Chrome, url: str):
        """Save cookies for future use."""
        domain = self._get_domain(url)
        cookies = driver.get_cookies()
        
        if cookies:
            cookie_file = self.cookies_dir / f"{domain}_cookies.json"
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)

    def _load_cookies(self, driver: webdriver.Chrome, url: str):
        """Load saved cookies for domain."""
        domain = self._get_domain(url)
        cookie_file = self.cookies_dir / f"{domain}_cookies.json"
        
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    driver.add_cookie(cookie)

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def scroll_page(self, driver: webdriver.Chrome, scroll_pause: float = 1.0):
        """Scroll page to load all content."""
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for content to load
            time.sleep(scroll_pause)
            
            # Calculate new scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
                
            last_height = new_height

    def wait_for_element(
        self,
        driver: webdriver.Chrome,
        selector: str,
        by: str = By.CSS_SELECTOR,
        timeout: int = 10,
        condition: str = "presence"
    ) -> Optional[webdriver.remote.webelement.WebElement]:
        """Wait for element with specified condition."""
        try:
            if condition == "presence":
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
            elif condition == "clickable":
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, selector))
                )
            elif condition == "visible":
                element = WebDriverWait(driver, timeout).until(
                    EC.visibility_of_element_located((by, selector))
                )
            else:
                raise ValueError(f"Unknown condition: {condition}")
                
            return element
            
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for element: {selector}")
            return None
        except Exception as e:
            self.logger.error(f"Error waiting for element {selector}: {e}")
            return None

    def safe_click(
        self,
        driver: webdriver.Chrome,
        element: webdriver.remote.webelement.WebElement,
        max_retries: int = 3
    ) -> bool:
        """Safely click element with retries."""
        for attempt in range(max_retries):
            try:
                # Scroll element into view
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                
                # Try regular click first
                element.click()
                return True
                
            except (StaleElementReferenceException, WebDriverException) as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to click element after {max_retries} attempts: {e}")
                    return False
                    
                time.sleep(1)
                continue
                
        return False

    def check_for_popups(self, driver: webdriver.Chrome):
        """Check and handle common popups."""
        popup_selectors = {
            'cookie_notice': [
                '//button[contains(text(), "Accept")]',
                '//button[contains(text(), "Got it")]'
            ],
            'newsletter': [
                '//button[contains(text(), "Close")]',
                '//div[contains(@class, "popup")]//button'
            ]
        }
        
        for popup_type, selectors in popup_selectors.items():
            for selector in selectors:
                try:
                    element = driver.find_element(By.XPATH, selector)
                    if element.is_displayed():
                        self.safe_click(driver, element)
                        self.logger.info(f"Handled {popup_type} popup")
                        time.sleep(0.5)
                except:
                    continue