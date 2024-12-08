# scraper/monitoring.py

import time
import psutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json
import threading
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import numpy as np
from collections import deque

class ScraperMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.metrics_dir = Path('logs/metrics')
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance metrics
        self.metrics = {
            # Scraping metrics
            'pages_scraped': Counter('pages_scraped_total', 'Total pages scraped'),
            'items_scraped': Counter('items_scraped_total', 'Total items scraped'),
            'scraping_errors': Counter('scraping_errors_total', 'Total scraping errors'),
            'scraping_duration': Histogram('scraping_duration_seconds', 
                                         'Time spent scraping pages',
                                         buckets=[10, 30, 60, 120, 300, 600]),
            
            # Resource usage
            'cpu_usage': Gauge('cpu_usage_percent', 'CPU usage percentage'),
            'memory_usage': Gauge('memory_usage_bytes', 'Memory usage in bytes'),
            'disk_usage': Gauge('disk_usage_bytes', 'Disk usage in bytes'),
            
            # Dataset metrics
            'dataset_size': Gauge('dataset_size_bytes', 'Dataset size in bytes'),
            'image_quality': Histogram('image_quality_score', 
                                     'Image quality scores',
                                     buckets=[0.1, 0.3, 0.5, 0.7, 0.9]),
            'caption_length': Histogram('caption_length', 
                                      'Caption lengths',
                                      buckets=[10, 20, 50, 100, 200]),
            
            # Performance metrics
            'request_latency': Histogram('request_latency_seconds',
                                       'Request latency',
                                       buckets=[0.1, 0.5, 1.0, 2.0, 5.0]),
            'success_rate': Gauge('success_rate_percent', 'Success rate percentage'),
        }
        
        # Performance tracking
        self.performance_window = 1000  # Track last 1000 requests
        self.request_times = deque(maxlen=self.performance_window)
        self.success_counts = deque(maxlen=self.performance_window)
        
        # Start metrics server
        start_http_server(8000)
        
        # Start monitoring thread
        self.stop_monitoring = False
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def track_scraping_start(self, url: str) -> float:
        """Track start of scraping for a URL."""
        start_time = time.time()
        self.metrics['pages_scraped'].inc()
        return start_time

    def track_scraping_end(self, start_time: float, success: bool = True):
        """Track end of scraping."""
        duration = time.time() - start_time
        self.metrics['scraping_duration'].observe(duration)
        self.request_times.append(duration)
        self.success_counts.append(1 if success else 0)
        
        # Update success rate
        if self.success_counts:
            success_rate = (sum(self.success_counts) / len(self.success_counts)) * 100
            self.metrics['success_rate'].set(success_rate)

    def track_item_scraped(self):
        """Track successful item scraping."""
        self.metrics['items_scraped'].inc()

    def track_error(self, error_type: str, error_message: str):
        """Track scraping error."""
        self.metrics['scraping_errors'].inc()
        
        # Log error details
        error_log = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message
        }
        
        error_file = self.metrics_dir / 'errors.jsonl'
        with open(error_file, 'a') as f:
            f.write(json.dumps(error_log) + '\n')

    def track_dataset_metrics(self, dataset_path: Path):
        """Track dataset quality metrics."""
        try:
            # Update dataset size
            total_size = sum(f.stat().st_size for f in dataset_path.rglob('*') if f.is_file())
            self.metrics['dataset_size'].set(total_size)
            
            # Track image quality scores
            quality_scores = self._analyze_image_quality(dataset_path)
            for score in quality_scores:
                self.metrics['image_quality'].observe(score)
            
            # Track caption lengths (for LLaVA dataset)
            caption_lengths = self._analyze_caption_lengths(dataset_path)
            for length in caption_lengths:
                self.metrics['caption_length'].observe(length)
                
        except Exception as e:
            self.logger.error(f"Error tracking dataset metrics: {e}")

    def _analyze_image_quality(self, dataset_path: Path) -> List[float]:
        """Analyze quality of images in dataset."""
        from PIL import Image
        import cv2
        
        quality_scores = []
        image_files = list(dataset_path.rglob('*.jpg'))
        
        for img_path in image_files:
            try:
                # Load image
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                
                # Convert to grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Calculate metrics
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()  # Sharpness
                brightness = np.mean(gray) / 255.0  # Brightness
                contrast = np.std(gray) / 128.0  # Contrast
                
                # Combine metrics into quality score
                quality_score = (
                    min(laplacian_var / 500, 1.0) * 0.4 +  # Sharpness (40%)
                    (1.0 - abs(0.5 - brightness)) * 0.3 +  # Brightness (30%)
                    min(contrast, 1.0) * 0.3  # Contrast (30%)
                )
                
                quality_scores.append(quality_score)
                
            except Exception as e:
                self.logger.error(f"Error analyzing image {img_path}: {e}")
                continue
                
        return quality_scores

    def _analyze_caption_lengths(self, dataset_path: Path) -> List[int]:
        """Analyze lengths of captions in LLaVA dataset."""
        caption_lengths = []
        json_files = list(dataset_path.rglob('*.json'))
        
        for json_path in json_files:
            try:
                with open(json_path) as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    for item in data:
                        if 'caption' in item:
                            caption_lengths.append(len(item['caption'].split()))
                            
            except Exception as e:
                self.logger.error(f"Error analyzing captions in {json_path}: {e}")
                continue
                
        return caption_lengths

    def _monitor_resources(self):
        """Monitor system resource usage."""
        while not self.stop_monitoring:
            try:
                # Update CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics['cpu_usage'].set(cpu_percent)
                
                # Update memory usage
                memory = psutil.Process().memory_info()
                self.metrics['memory_usage'].set(memory.rss)
                
                # Update disk usage
                disk = psutil.disk_usage('/')
                self.metrics['disk_usage'].set(disk.used)
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error monitoring resources: {e}")
                time.sleep(5)
                continue

    def get_performance_stats(self) -> Dict:
        """Get current performance statistics."""
        stats = {
            'scraping': {
                'total_pages': self.metrics['pages_scraped']._value.get(),
                'total_items': self.metrics['items_scraped']._value.get(),
                'total_errors': self.metrics['scraping_errors']._value.get(),
                'success_rate': self.metrics['success_rate']._value,
                'avg_duration': np.mean(self.request_times) if self.request_times else 0
            },
            'resources': {
                'cpu_usage': self.metrics['cpu_usage']._value,
                'memory_usage': self.metrics['memory_usage']._value,
                'disk_usage': self.metrics['disk_usage']._value
            },
            'dataset': {
                'size': self.metrics['dataset_size']._value,
                'avg_quality': self._get_histogram_mean(self.metrics['image_quality']),
                'avg_caption_length': self._get_histogram_mean(self.metrics['caption_length'])
            }
        }
        
        return stats

    def _get_histogram_mean(self, histogram) -> float:
        """Calculate mean value from histogram."""
        if not histogram._sum.get() or not histogram._count.get():
            return 0
        return histogram._sum.get() / histogram._count.get()

    def stop(self):
        """Stop monitoring."""
        self.stop_monitoring = True
        if self.monitor_thread.is_alive():
            self.monitor_thread.join()

# Example usage:
if __name__ == '__main__':
    from config import ScraperConfig
    
    # Initialize monitor
    config = ScraperConfig()
    monitor = ScraperMonitor(config.config)
    
    # Track scraping
    start_time = monitor.track_scraping_start("https://example.com")
    try:
        # Simulated scraping
        time.sleep(2)
        monitor.track_item_scraped()
        monitor.track_scraping_end(start_time, success=True)
    except Exception as e:
        monitor.track_error("scraping_error", str(e))
        monitor.track_scraping_end(start_time, success=False)
    
    # Get statistics
    stats = monitor.get_performance_stats()
    print(json.dumps(stats, indent=2))
    
    # Stop monitoring
    monitor.stop()