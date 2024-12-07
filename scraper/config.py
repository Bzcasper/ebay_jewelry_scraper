# scraper/config.py

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
import yaml
from datetime import datetime

class JewelryCategory(BaseModel):
    """Model for jewelry category configuration."""
    main_class: str
    subcategories: List[str]
    enabled: bool = True
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    
    @validator('main_class')
    def validate_main_class(cls, v):
        valid_classes = ['necklace', 'pendant', 'bracelet', 'ring', 'earring', 'wristwatch']
        if v.lower() not in valid_classes:
            raise ValueError(f"main_class must be one of {valid_classes}")
        return v.lower()

class ScrapingLimits(BaseModel):
    """Model for scraping rate limits and quotas."""
    max_pages_per_category: int = Field(default=10, ge=1, le=100)
    max_items_per_page: int = Field(default=48, ge=1, le=100)
    max_concurrent_requests: int = Field(default=4, ge=1, le=10)
    request_delay: float = Field(default=1.5, ge=0.5)
    max_retries: int = Field(default=3, ge=1)
    timeout: int = Field(default=30, ge=10)

class ImageConfig(BaseModel):
    """Model for image processing configuration."""
    min_width: int = Field(default=400, ge=200)
    min_height: int = Field(default=400, ge=200)
    max_size_mb: float = Field(default=10.0, ge=0.1)
    required_formats: List[str] = ['JPEG', 'JPG', 'PNG']
    resize_dimensions: Dict[str, tuple] = {
        'resnet': (224, 224),
        'llava': (512, 512)
    }

class DatasetConfig(BaseModel):
    """Model for dataset creation configuration."""
    train_split: float = Field(default=0.7, ge=0.5, le=0.9)
    val_split: float = Field(default=0.15, ge=0.05, le=0.25)
    test_split: float = Field(default=0.15, ge=0.05, le=0.25)
    min_samples_per_class: int = Field(default=100, ge=50)
    balance_classes: bool = True
    augmentation_factor: int = Field(default=3, ge=1)

class ScraperConfig(BaseModel):
    """Main configuration model for the scraper."""
    # Base settings
    output_dir: Path = Field(default=Path("jewelry_dataset"))
    debug_mode: bool = Field(default=False)
    use_proxy: bool = Field(default=False)
    
    # Category configuration
    categories: List[JewelryCategory] = Field(default=[
        JewelryCategory(
            main_class="necklace",
            subcategories=["Choker", "Pendant", "Chain"]
        ),
        JewelryCategory(
            main_class="pendant",
            subcategories=["Heart", "Cross", "Star"]
        ),
        JewelryCategory(
            main_class="bracelet",
            subcategories=["Tennis", "Charm", "Bangle"]
        ),
        JewelryCategory(
            main_class="ring",
            subcategories=["Engagement", "Wedding", "Fashion"]
        ),
        JewelryCategory(
            main_class="earring",
            subcategories=["Stud", "Hoop", "Drop"]
        ),
        JewelryCategory(
            main_class="wristwatch",
            subcategories=["Analog", "Digital", "Smart"]
        )
    ])
    
    # Component configurations
    scraping_limits: ScrapingLimits = Field(default_factory=ScrapingLimits)
    image_config: ImageConfig = Field(default_factory=ImageConfig)
    dataset_config: DatasetConfig = Field(default_factory=DatasetConfig)
    
    # Selenium configuration
    selenium_config: Dict = Field(default={
        "headless": True,
        "window_size": (1920, 1080),
        "page_load_timeout": 30,
        "implicit_wait": 10
    })
    
    class Config:
        arbitrary_types_allowed = True

    @validator('output_dir', pre=True)
    def validate_output_dir(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, filepath: Union[str, Path] = None) -> None:
        """Save configuration to file."""
        if filepath is None:
            filepath = self.output_dir / f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dictionary and handle Path objects
        config_dict = self.dict()
        config_dict['output_dir'] = str(config_dict['output_dir'])
        
        with open(filepath, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> 'ScraperConfig':
        """Load configuration from file."""
        with open(filepath, 'r') as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)

    def update_from_env(self) -> None:
        """Update configuration from environment variables."""
        env_prefix = 'SCRAPER_'
        for var_name, var_value in os.environ.items():
            if var_name.startswith(env_prefix):
                config_key = var_name[len(env_prefix):].lower()
                self._update_nested_config(config_key, var_value)

    def _update_nested_config(self, key: str, value: str) -> None:
        """Update nested configuration values."""
        keys = key.split('_')
        current = self
        
        for k in keys[:-1]:
            if hasattr(current, k):
                current = getattr(current, k)
            else:
                return
        
        if hasattr(current, keys[-1]):
            setattr(current, keys[-1], self._convert_value(value))

    def _convert_value(self, value: str) -> Union[str, int, float, bool, list]:
        """Convert string values to appropriate types."""
        # Try boolean
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try list (comma-separated)
        if ',' in value:
            return [v.strip() for v in value.split(',')]
        
        return value

    def validate_and_lock(self) -> None:
        """Validate configuration and prevent further modifications."""
        # Validate splits sum to 1
        splits_sum = (self.dataset_config.train_split + 
                     self.dataset_config.val_split + 
                     self.dataset_config.test_split)
        if not 0.99 <= splits_sum <= 1.01:
            raise ValueError("Dataset splits must sum to 1.0")
        
        # Validate categories
        total_subcategories = sum(len(cat.subcategories) for cat in self.categories)
        if total_subcategories < self.dataset_config.min_samples_per_class:
            raise ValueError(
                f"Total subcategories ({total_subcategories}) must be >= "
                f"min_samples_per_class ({self.dataset_config.min_samples_per_class})"
            )

        # Make configuration immutable
        for field in self.__fields__:
            value = getattr(self, field)
            if isinstance(value, (list, dict)):
                setattr(self, field, value.copy())

    def get_enabled_categories(self) -> List[JewelryCategory]:
        """Get list of enabled categories."""
        return [cat for cat in self.categories if cat.enabled]

    def get_category_config(self, category_name: str) -> Optional[JewelryCategory]:
        """Get configuration for a specific category."""
        for category in self.categories:
            if category.main_class == category_name.lower():
                return category
        return None

# Example usage:
if __name__ == "__main__":
    # Create default configuration
    config = ScraperConfig()
    
    # Update from environment variables
    config.update_from_env()
    
    # Save configuration
    config.save("scraper_config.yaml")
    
    # Load configuration
    loaded_config = ScraperConfig.load("scraper_config.yaml")
    
    # Validate and lock configuration
    loaded_config.validate_and_lock()