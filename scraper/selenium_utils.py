# scraper/selenium_utils.py

import os
import logging
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional, List
from bs4 import BeautifulSoup

def setup_selenium_driver(proxies: Optional[List[str]] = None, user_agent: Optional[str] = None) -> webdriver.Chrome:
    """
    Configure and initialize Selenium WebDriver with proxy rotation and user-agent spoofing

    Args:
        proxies (Optional[List[str]]): List of proxy server addresses in the format "http://ip:port".
        user_agent (Optional[str]): Custom user-agent string to spoof browser identity.

    Returns:
        webdriver.Chrome: Configured Selenium WebDriver instance.

    Raises:
        WebDriverException: If the WebDriver fails to initialize.
    """
    options = Options()
    
    # Headless mode configuration
    headless = os.getenv('HEADLESS', 'True').lower() in ['true', '1', 't']
    if headless:
        options.add_argument('--headless')
        logging.info("Running Chrome in headless mode.")
    else:
        logging.info("Running Chrome in headed mode.")
    
    # Essential options
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Enhanced anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Set user-agent if provided
    if user_agent:
        options.add_argument(f'user-agent={user_agent}')
        logging.info(f"Using custom User-Agent: {user_agent}")
    
    # Set proxy if provided
    if proxies:
        proxy = proxies[0]  # Use the first proxy in the list
        options.add_argument(f'--proxy-server={proxy}')
        logging.info(f"Using proxy server: {proxy}")
    
    # Additional privacy options
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    
    try:
        # Initialize WebDriver with ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # Execute stealth JavaScript to hide automation flags
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3],
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            '''
        })
        
        logging.info("Selenium WebDriver initialized successfully.")
        return driver
    
    except WebDriverException as e:
        logging.error(f"Failed to initialize Selenium WebDriver: {e}")
        raise

def safe_get_url(driver: webdriver.Chrome, url: str, max_retries: int = 3, wait_time: int = 5) -> bool:
    """
    Safely navigate to URL with retries and improved waiting

    Args:
        driver (webdriver.Chrome): Selenium WebDriver instance.
        url (str): URL to navigate to.
        max_retries (int): Maximum number of retry attempts.
        wait_time (int): Time to wait (in seconds) after each navigation.

    Returns:
        bool: True if navigation and element loading are successful, False otherwise.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Navigating to URL: {url} (Attempt {attempt})")
            driver.get(url)
            
            # Wait for key elements (e.g., product listings) to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-item"))
            )
            
            # Additional wait for dynamic content
            time.sleep(wait_time)
            
            # Scroll the page to load lazy-loaded content
            scroll_page(driver)
            
            logging.info(f"Successfully navigated to {url}")
            return True
            
        except (TimeoutException, WebDriverException) as e:
            logging.warning(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                backoff_time = 2 ** attempt
                logging.info(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
            else:
                logging.error(f"All {max_retries} attempts to navigate to {url} have failed.")
                return False

    return False

def check_for_captcha(driver: webdriver.Chrome) -> bool:
    """
    Enhanced CAPTCHA detection

    Args:
        driver (webdriver.Chrome): Selenium WebDriver instance.

    Returns:
        bool: True if CAPTCHA is detected, False otherwise.
    """
    captcha_indicators = [
        "enter the characters you see below",
        "security verification",
        "are you a human",
        "detected unusual activity",
        "please verify you're a human",
        "please confirm you are a human"
    ]
    
    try:
        # Check for CAPTCHA elements
        captcha_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='captcha'], [id*='captcha'], [name*='captcha']")
        if captcha_elements:
            logging.warning("CAPTCHA element detected on the page.")
            return True
        
        # Check for text indicators in the page source
        page_source = driver.page_source.lower()
        for indicator in captcha_indicators:
            if indicator in page_source:
                logging.warning(f"CAPTCHA indicator detected: '{indicator}'")
                return True
                
    except Exception as e:
        logging.error(f"Error during CAPTCHA detection: {e}")
    
    return False

def scroll_page(driver: webdriver.Chrome, pause_time: float = 1.0):
    """
    Improved page scrolling with dynamic content loading

    Args:
        driver (webdriver.Chrome): Selenium WebDriver instance.
        pause_time (float): Time to wait after each scroll action.
    """
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        logging.info("Starting to scroll the page for dynamic content.")
    
        while True:
            # Scroll down to the bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            logging.debug("Scrolled to the bottom of the page.")
            time.sleep(pause_time)
    
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logging.info("Reached the bottom of the page. Scrolling complete.")
                break
            last_height = new_height
    
    except Exception as e:
        logging.error(f"Error during page scrolling: {e}")

def wait_for_element(driver: webdriver.Chrome, selector: str, by: By = By.CSS_SELECTOR, timeout: int = 10) -> Optional[webdriver.remote.webelement.WebElement]:
    """
    Wait for an element to be present and visible

    Args:
        driver (webdriver.Chrome): Selenium WebDriver instance.
        selector (str): CSS selector of the element to wait for.
        by (By): Method to locate elements (default is CSS_SELECTOR).
        timeout (int): Maximum time to wait (in seconds).

    Returns:
        Optional[WebElement]: The located WebElement if found, None otherwise.
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, selector))
        )
        logging.info(f"Element '{selector}' is present and visible.")
        return element
    except TimeoutException:
        logging.error(f"Timeout waiting for element: '{selector}'")
    except NoSuchElementException:
        logging.error(f"Element not found: '{selector}'")
    except Exception as e:
        logging.error(f"Unexpected error while waiting for element '{selector}': {e}")
    return None
