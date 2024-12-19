# scraper/selenium_utils.py

import os
import time
import random
import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    WINDOW_SIZE,
    USER_AGENT,
    PAGE_LOAD_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChromeManager:
    """Manages Chrome browser detection and setup"""

    @staticmethod
    def get_chrome_path() -> Optional[str]:
        """Get Chrome browser path based on operating system"""
        system = platform.system().lower()

        if system == "windows":
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
            ]
        elif system == "darwin":  # macOS
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            ]
        else:  # Linux
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable"
            ]

        for path in chrome_paths:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def get_chrome_version(chrome_path: Optional[str] = None) -> Optional[str]:
        """Get Chrome version number"""
        try:
            if not chrome_path:
                chrome_path = ChromeManager.get_chrome_path()

            if not chrome_path:
                return None

            if platform.system().lower() == "windows":
                cmd = f'wmic datafile where name="{chrome_path.replace("\\", "\\\\")}" get Version /value'
            else:
                cmd = f'"{chrome_path}" --version'

            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            version = result.stdout.strip()

            # Extract version number
            import re
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version)
            return match.group(1) if match else None

        except Exception as e:
            logger.error(f"Error getting Chrome version: {e}")
            return None

class BrowserSetup:
    """Handles browser configuration and anti-detection measures"""

    @staticmethod
    def create_chrome_options() -> Options:
        """Create Chrome options with anti-detection measures"""
        options = Options()

        # Performance settings
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-features=NetworkService')
        options.add_argument(f'--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}')

        # Anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Removed the following lines to fix the Chrome option error
        # options.add_experimental_option('excludeSwitches', ['enable-automation'])
        # options.add_experimental_option('useAutomationExtension', False)

        # Add realistic user agent
        options.add_argument(f'user-agent={USER_AGENT}')

        # Additional privacy settings
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')

        return options

    @staticmethod
    def inject_stealth_js(driver: webdriver.Chrome) -> None:
        """Inject JavaScript to avoid detection"""
        stealth_js = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
        try:
            driver.execute_script(stealth_js)
        except Exception as e:
            logger.warning(f"Failed to inject stealth JS: {e}")

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_DELAY),
    retry=retry_if_exception_type(WebDriverException)
)
def setup_selenium_driver() -> Optional[webdriver.Chrome]:
    """Initialize and configure Chrome WebDriver with retry logic"""
    try:
        chrome_path = ChromeManager.get_chrome_path()
        options = BrowserSetup.create_chrome_options()

        if chrome_path:
            options.binary_location = chrome_path

        # Use undetected-chromedriver for better anti-detection
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        # Inject stealth JavaScript
        BrowserSetup.inject_stealth_js(driver)

        # Test connection
        driver.get("https://www.ebay.com")
        time.sleep(random.uniform(2, 4))

        logger.info("Selenium WebDriver initialized successfully.")
        return driver

    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {e}")
        if 'driver' in locals():
            driver.quit()
        raise  # Propagate exception for retry

def check_for_captcha(driver: webdriver.Chrome) -> bool:
    """Enhanced CAPTCHA detection"""
    try:
        # Check URL and page source
        current_url = driver.current_url.lower()
        page_source = driver.page_source.lower()

        captcha_indicators = [
            "captcha",
            "security check",
            "verify human",
            "bot detection",
            "unusual activity",
            "prove you're human"
        ]

        # Check for indicators
        for indicator in captcha_indicators:
            if indicator in page_source or indicator in current_url:
                logger.warning(f"CAPTCHA detected: {indicator}")
                return True

        return False

    except Exception as e:
        logger.error(f"Error checking for CAPTCHA: {e}")
        return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1)
)
def wait_for_element(
    driver: webdriver.Chrome,
    selector: str,
    by: By = By.CSS_SELECTOR,
    timeout: int = 10,
    condition: str = "presence"
) -> Optional[webdriver.remote.webelement.WebElement]:
    """Wait for element with multiple conditions and retry logic"""
    try:
        wait = WebDriverWait(driver, timeout)

        conditions = {
            "presence": EC.presence_of_element_located,
            "clickable": EC.element_to_be_clickable,
            "visible": EC.visibility_of_element_located
        }

        if condition not in conditions:
            raise ValueError(f"Unknown condition: {condition}")

        element = wait.until(conditions[condition]((by, selector)))
        return element

    except Exception as e:
        logger.error(f"Error waiting for element {selector}: {e}")
        raise  # Propagate exception for retry

def scroll_page(driver: webdriver.Chrome, pause_time: float = 1.0) -> None:
    """Smooth scroll page to load dynamic content"""
    try:
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        scroll_steps = 10

        for step in range(scroll_steps):
            scroll_amount = (step + 1) * total_height / scroll_steps
            driver.execute_script(f"window.scrollTo(0, {scroll_amount})")
            time.sleep(pause_time / scroll_steps)

            # Random mouse movement
            simulate_mouse_movement(driver)

        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(random.uniform(1, 2))

    except Exception as e:
        logger.error(f"Error scrolling page: {e}")

def simulate_mouse_movement(driver: webdriver.Chrome) -> None:
    """Simulate realistic mouse movements"""
    try:
        script = """
            var event = new MouseEvent('mousemove', {
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': arguments[0],
                'clientY': arguments[1]
            });
            document.dispatchEvent(event);
        """
        x = random.randint(0, WINDOW_SIZE[0])
        y = random.randint(0, WINDOW_SIZE[1])
        driver.execute_script(script, x, y)
    except Exception as e:
        logger.debug(f"Error simulating mouse movement: {e}")

def safe_get_url(driver: webdriver.Chrome, url: str) -> bool:
    """Safely navigate to a URL with error handling"""
    try:
        driver.get(url)
        logging.info(f"Navigated to {url}")
        return True
    except WebDriverException as e:
        logger.error(f"Failed to navigate to {url}: {e}")
        return False
