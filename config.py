# config.py

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import logging
from datetime import datetime

class ScraperConfig:
    """Configuration management for the jewelry scraping pipeline."""
    
    def __init__(self, config_path: Optional[str] = None):
        # Default configuration
        self.default_config = {
            'scraper': {
                'output_dir': 'jewelry_dataset',
                'max_items_per_category': 1000,
                'max_pages_per_category': 50,
                'max_retries': 3,
                'delay_between_requests': 1.5,
                'timeout': 30,
                'max_concurrent_requests': 4,
                'browser_settings': {
                    'headless': True,
                    'window_size': (1920, 1080),
                    'user_agent_rotation': True,
                    'proxy_rotation': True
                }
            },
            'dataset': {
                'resnet': {
                    'image_size': (224, 224),
                    'batch_size': 32,
                    'train_split': 0.7,
                    'val_split': 0.15,
                    'test_split': 0.15,
                    'augmentation_factor': 3,
                    'normalize_mean': [0.485, 0.456, 0.406],
                    'normalize_std': [0.229, 0.224, 0.225]
                },
                'llava': {
                    'image_size': (512, 512),
                    'max_caption_length': 256,
                    'min_caption_length': 10,
                    'train_split': 0.7,
                    'val_split': 0.15,
                    'test_split': 0.15
                }
            },
            'categories': {
                'necklace': ['Choker', 'Pendant', 'Chain'],
                'pendant': ['Heart', 'Cross', 'Star'],
                'bracelet': ['Tennis', 'Charm', 'Bangle'],
                'ring': ['Engagement', 'Wedding', 'Fashion'],
                'earring': ['Stud', 'Hoop', 'Drop'],
                'wristwatch': ['Analog', 'Digital', 'Smart']
            },
            'storage': {
                'raw_data_dir': 'raw_data',
                'processed_data_dir': 'processed_data',
                'dataset_dir': 'datasets',
                'logs_dir': 'logs',
                'max_raw_size_gb': 100,
                'cleanup_threshold_gb': 80
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_rotation': '1 day',
                'max_log_files': 30
            },
            'api': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': True,
                'max_upload_size_mb': 10
            }
        }
        
        # Load custom config if provided
        self.config = self.default_config.copy()
        if config_path:
            self.load_config(config_path)
            
        # Setup directories
        self.setup_directories()
        
        # Initialize logging
        self.setup_logging()

    def load_config(self, config_path: str) -> None:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                custom_config = yaml.safe_load(f)
                
            # Deep update of default config
            self._deep_update(self.config, custom_config)
            
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {e}")
            logging.info("Using default configuration")

    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Recursively update nested dictionary."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def setup_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.config['storage']['raw_data_dir'],
            self.config['storage']['processed_data_dir'],
            self.config['storage']['dataset_dir'],
            self.config['storage']['logs_dir'],
            'config'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def setup_logging(self) -> None:
        """Configure logging system."""
        log_config = self.config['logging']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = Path(self.config['storage']['logs_dir']) / f'scraper_{timestamp}.log'
        
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['format'],
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def get_scraper_config(self) -> Dict[str, Any]:
        """Get scraper-specific configuration."""
        return self.config['scraper']

    def get_dataset_config(self, model_type: str) -> Dict[str, Any]:
        """Get dataset configuration for specific model."""
        return self.config['dataset'][model_type]

    def get_categories(self) -> Dict[str, list]:
        """Get configured categories and subcategories."""
        return self.config['categories']

    def save_config(self, filepath: str) -> None:
        """Save current configuration to file."""
        try:
            with open(filepath, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            logging.error(f"Error saving config to {filepath}: {e}")

    def update_category(self, main_category: str, subcategories: Optional[list] = None) -> None:
        """Update category configuration."""
        if subcategories is None:
            subcategories = []
            
        self.config['categories'][main_category] = subcategories
        self.save_current_config()

    def remove_category(self, main_category: str) -> None:
        """Remove category from configuration."""
        if main_category in self.config['categories']:
            del self.config['categories'][main_category]
            self.save_current_config()

    def save_current_config(self) -> None:
        """Save current configuration to default location."""
        config_file = Path('config/current_config.yaml')
        self.save_config(str(config_file))

    def validate_config(self) -> bool:
        """Validate current configuration."""
        try:
            # Check dataset splits sum to 1
            for model in ['resnet', 'llava']:
                splits = [
                    self.config['dataset'][model]['train_split'],
                    self.config['dataset'][model]['val_split'],
                    self.config['dataset'][model]['test_split']
                ]
                if abs(sum(splits) - 1.0) > 0.001:
                    raise ValueError(f"Dataset splits for {model} must sum to 1.0")
            
            # Check directory permissions
            for dir_path in [
                self.config['storage']['raw_data_dir'],
                self.config['storage']['processed_data_dir'],
                self.config['storage']['dataset_dir'],
                self.config['storage']['logs_dir']
            ]:
                if not os.access(dir_path, os.W_OK):
                    raise PermissionError(f"No write access to {dir_path}")
            
            # Validate category structure
            if not isinstance(self.config['categories'], dict):
                raise ValueError("Categories must be a dictionary")
            
            for category, subcategories in self.config['categories'].items():
                if not isinstance(subcategories, list):
                    raise ValueError(f"Subcategories for {category} must be a list")
            
            return True
            
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics."""
        stats = {}
        for dir_name, dir_path in [
            ('raw_data', self.config['storage']['raw_data_dir']),
            ('processed_data', self.config['storage']['processed_data_dir']),
            ('datasets', self.config['storage']['dataset_dir'])
        ]:
            total_size = sum(
                f.stat().st_size for f in Path(dir_path).rglob('*') if f.is_file()
            )
            stats[dir_name] = {
                'size_gb': total_size / (1024 ** 3),
                'file_count': sum(1 for _ in Path(dir_path).rglob('*') if _.is_file())
            }
            
        return stats

    def should_cleanup_storage(self) -> bool:
        """Check if storage cleanup is needed."""
        stats = self.get_storage_stats()
        total_size_gb = sum(s['size_gb'] for s in stats.values())
        return total_size_gb > self.config['storage']['cleanup_threshold_gb']

# Example usage:
if __name__ == '__main__':
    config = ScraperConfig()
    
    # Validate configuration
    if config.validate_config():
        print("Configuration is valid")
        
        # Save current config
        config.save_current_config()
        
        # Get storage stats
        stats = config.get_storage_stats()
        print("\nStorage Statistics:")
        for dir_name, dir_stats in stats.items():
            print(f"{dir_name}:")
            print(f"  Size: {dir_stats['size_gb']:.2f} GB")
            print(f"  Files: {dir_stats['file_count']}")