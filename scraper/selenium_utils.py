from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time

def setup_selenium_driver():
    """Configure and initialize Selenium WebDriver with improved settings"""
    options = Options()
    
    # Comment out headless mode for debugging
    # options.add_argument('--headless')
    
    # Essential options
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Enhanced anti-detection measures
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Set realistic user agent
    user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                 'AppleWebKit/537.36 (KHTML, like Gecko) '
                 'Chrome/120.0.0.0 Safari/537.36')
    options.add_argument(f'user-agent={user_agent}')
    
    # Additional privacy options
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # Set initial cookies and perform setup
        driver.get("https://www.ebay.com")
        time.sleep(3)  # Increased initial wait time
        
        # Execute stealth JavaScript
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
        
    except Exception as e:
        logging.error(f"Failed to initialize Selenium: {str(e)}")
        raise

def safe_get_url(driver, url, max_retries=3):
    """Safely navigate to URL with retries and improved waiting"""
    for attempt in range(max_retries):
        try:
            driver.get(url)
            
            # Wait for key elements
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-item"))
            )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Scroll for lazy-loaded content
            scroll_page(driver)
            
            return True
            
        except Exception as e:
            logging.error(f"Error navigating to {url} (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return False

def check_for_captcha(driver):
    """Enhanced CAPTCHA detection"""
    captcha_indicators = [
        "/.*/distil_identify_cookie.html.*",
        "/.*/distil_r_captcha.html.*",
        "Enter the characters you see below",
        "Security Verification",
        "Are you a human?",
        "detected unusual activity",
        "please verify you're a human",
        "Please confirm you are a human"
    ]
    
    # Check both URL and page source
    page_source = driver.page_source.lower()
    current_url = driver.current_url.lower()
    
    # Check for CAPTCHA elements
    try:
        captcha_elements = driver.find_elements(By.CSS_SELECTOR, 
            "[class*='captcha'], [id*='captcha'], [name*='captcha']")
        if captcha_elements:
            return True
    except:
        pass
    
    for indicator in captcha_indicators:
        if indicator.lower() in page_source or indicator.lower() in current_url:
            return True
            
    return False

def scroll_page(driver, pause_time=1):
    """Improved page scrolling with dynamic content loading"""
    try:
        # Initial pause for page load
        time.sleep(2)
        
        # Get initial scroll height
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll in smaller increments
            for i in range(3):
                driver.execute_script(
                    f"window.scrollTo(0, {(i+1) * last_height/3});")
                time.sleep(pause_time)
            
            # Calculate new scroll height and check if we've reached the bottom
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        # Scroll back to top (sometimes helps load all content)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(pause_time)
        
    except Exception as e:
        logging.error(f"Error scrolling page: {str(e)}")

def wait_for_element(driver, selector, by=By.CSS_SELECTOR, timeout=10):
    """Wait for an element to be present and visible"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except Exception as e:
        logging.error(f"Timeout waiting for element {selector}: {str(e)}")
        return None