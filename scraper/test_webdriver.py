# scraper/test_webdriver.py

import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import undetected_chromedriver as uc

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_driver():
    try:
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " \
                     "AppleWebKit/537.36 (KHTML, like Gecko) " \
                     "Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')

        # Initialize undetected-chromedriver
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(30)

        # Inject stealth JavaScript
        stealth_js = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
        driver.execute_script(stealth_js)

        # Test connection
        driver.get("https://www.ebay.com")
        logger.info("WebDriver initialized and navigated to eBay successfully.")
        driver.quit()
    except WebDriverException as e:
        logger.error(f"WebDriver initialization failed: {e}")

if __name__ == "__main__":
    test_driver()
