# scraper/debug_scraper.py

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import pandas as pd
from collections import defaultdict

class ScraperDebugger:
    def __init__(self, output_dir: str = "debug_output"):
        self.output_dir = Path(output_dir)
        self.debug_dir = self.output_dir / "debug_logs"
        self.html_dir = self.output_dir / "html_snapshots"
        self.screenshot_dir = self.output_dir / "screenshots"
        
        # Create necessary directories
        for directory in [self.debug_dir, self.html_dir, self.screenshot_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger('scraper_debug')
        self.setup_debug_logging()
        
        # Initialize stats tracking
        self.stats = defaultdict(int)
        self.errors = defaultdict(list)
        self.timings = defaultdict(list)

    def setup_debug_logging(self):
        """Configure debug-specific logging."""
        debug_log_path = self.debug_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        handler = logging.FileHandler(debug_log_path)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def test_page_load(self, url: str, driver: webdriver.Chrome) -> Dict:
        """Test page load performance and capture issues."""
        results = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'load_time': 0,
            'status': 'unknown',
            'errors': [],
            'resources': defaultdict(int)
        }
        
        try:
            start_time = time.time()
            driver.get(url)
            
            # Wait for page load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            results['load_time'] = time.time() - start_time
            results['status'] = 'success'
            
            # Capture performance metrics
            performance = driver.execute_script("return window.performance.timing.toJSON()")
            results['performance'] = {
                'dns': performance['domainLookupEnd'] - performance['domainLookupStart'],
                'connect': performance['connectEnd'] - performance['connectStart'],
                'response': performance['responseEnd'] - performance['responseStart'],
                'dom_load': performance['domContentLoadedEventEnd'] - performance['navigationStart'],
                'page_load': performance['loadEventEnd'] - performance['navigationStart']
            }
            
            # Count resource types
            resources = driver.execute_script("""
                return performance.getEntriesByType('resource').map(
                    e => ({type: e.initiatorType, duration: e.duration})
                );
            """)
            
            for resource in resources:
                results['resources'][resource['type']] += 1
            
            # Take screenshot
            self._save_screenshot(driver, url)
            
            # Save page source
            self._save_page_source(driver.page_source, url)
            
        except Exception as e:
            results['status'] = 'error'
            results['errors'].append(str(e))
            self.logger.error(f"Error testing page load for {url}: {e}")
        
        return results

    def validate_selectors(self, html: str, selectors: Dict[str, List[str]]) -> Dict:
        """Validate all selectors against HTML content."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'total_selectors': sum(len(s) for s in selectors.values()),
            'working_selectors': 0,
            'failed_selectors': [],
            'selector_results': {}
        }
        
        soup = BeautifulSoup(html, 'html.parser')
        
        for element_type, selector_list in selectors.items():
            results['selector_results'][element_type] = {
                'working': [],
                'failed': []
            }
            
            for selector in selector_list:
                try:
                    elements = soup.select(selector)
                    if elements:
                        results['working_selectors'] += 1
                        results['selector_results'][element_type]['working'].append(selector)
                    else:
                        results['failed_selectors'].append(selector)
                        results['selector_results'][element_type]['failed'].append(selector)
                except Exception as e:
                    self.logger.error(f"Error validating selector {selector}: {e}")
                    results['failed_selectors'].append(selector)
                    results['selector_results'][element_type]['failed'].append(selector)
        
        return results

    def analyze_product_data(self, product: Dict) -> Dict:
        """Analyze extracted product data for completeness and validity."""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'product_url': product.get('url', 'unknown'),
            'completeness': {},
            'validation_errors': [],
            'warnings': []
        }
        
        # Required fields
        required_fields = ['title', 'price', 'image_url', 'category']
        optional_fields = ['condition', 'shipping', 'seller', 'description']
        
        # Check required fields
        for field in required_fields:
            if field not in product or not product[field]:
                analysis['validation_errors'].append(f"Missing required field: {field}")
            
        # Check data types and values
        if 'price' in product:
            try:
                price = float(product['price'])
                if price <= 0:
                    analysis['validation_errors'].append("Invalid price value")
            except (ValueError, TypeError):
                analysis['validation_errors'].append("Invalid price format")
                
        # Calculate completeness
        total_fields = len(required_fields) + len(optional_fields)
        present_fields = sum(1 for f in required_fields + optional_fields if f in product and product[f])
        analysis['completeness'] = {
            'score': round(present_fields / total_fields * 100, 2),
            'present_fields': present_fields,
            'total_fields': total_fields
        }
        
        return analysis

    def _save_screenshot(self, driver: webdriver.Chrome, url: str):
        """Save page screenshot with timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"screenshot_{timestamp}_{self._clean_filename(url)}.png"
        driver.save_screenshot(str(self.screenshot_dir / filename))

    def _save_page_source(self, html: str, url: str):
        """Save page source with timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"page_{timestamp}_{self._clean_filename(url)}.html"
        
        with open(self.html_dir / filename, 'w', encoding='utf-8') as f:
            f.write(html)

    def _clean_filename(self, url: str) -> str:
        """Clean URL for use in filename."""
        return "".join(c if c.isalnum() else '_' for c in url)[:50]

    def generate_debug_report(self) -> str:
        """Generate comprehensive debug report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': dict(self.stats),
            'errors': dict(self.errors),
            'timings': {
                k: {
                    'min': min(v),
                    'max': max(v),
                    'avg': sum(v) / len(v)
                } for k, v in self.timings.items() if v
            }
        }
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.debug_dir / f"debug_report_{timestamp}.json"
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        return str(report_path)

    def analyze_errors(self) -> pd.DataFrame:
        """Analyze error patterns and frequencies."""
        error_data = []
        
        for error_type, instances in self.errors.items():
            error_data.append({
                'error_type': error_type,
                'count': len(instances),
                'first_occurrence': min(inst['timestamp'] for inst in instances),
                'last_occurrence': max(inst['timestamp'] for inst in instances),
                'urls_affected': len(set(inst['url'] for inst in instances))
            })
            
        return pd.DataFrame(error_data)

    def test_selectors(self, html: str, selectors: Dict[str, List[str]]) -> None:
        """Interactive selector testing utility."""
        soup = BeautifulSoup(html, 'html.parser')
        
        print("\nSelector Testing Results:")
        print("-" * 50)
        
        for element_type, selector_list in selectors.items():
            print(f"\nTesting {element_type} selectors:")
            
            for selector in selector_list:
                try:
                    elements = soup.select(selector)
                    print(f"\nSelector: {selector}")
                    print(f"Found {len(elements)} elements")
                    
                    if elements:
                        # Show first element content
                        content = elements[0].get_text(strip=True)
                        print(f"First element content: {content[:100]}...")
                    
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")

    def monitor_performance(self, url: str, driver: webdriver.Chrome) -> Dict:
        """Monitor page performance metrics."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'load_time': 0,
            'memory_usage': {},
            'network_requests': 0,
            'errors': []
        }
        
        try:
            start_time = time.time()
            driver.get(url)
            metrics['load_time'] = time.time() - start_time
            
            # Get memory info
            memory_info = driver.execute_script('return window.performance.memory;')
            metrics['memory_usage'] = {
                'total_js_heap_size': memory_info['totalJSHeapSize'],
                'used_js_heap_size': memory_info['usedJSHeapSize']
            }
            
            # Get network requests
            network_requests = driver.execute_script(
                'return window.performance.getEntriesByType("resource");'
            )
            metrics['network_requests'] = len(network_requests)
            
        except Exception as e:
            metrics['errors'].append(str(e))
            
        return metrics