# config.py
from dataclasses import dataclass, field
from typing import List, Dict
import json

@dataclass
class ScraperConfig:
    output_dir: str = "jewelry_dataset"
    max_items: int = 100  # Maximum items per subcategory
    max_pages: int = 5    # Maximum pages per subcategory
    categories: List[Dict] = field(default_factory=lambda: [
        {'main_class': 'Necklace', 'subcategories': ['Choker', 'Pendant', 'Chain']},
        {'main_class': 'Pendant', 'subcategories': ['Heart', 'Cross', 'Star']},
        {'main_class': 'Bracelet', 'subcategories': ['Tennis', 'Charm', 'Bangle']},
        {'main_class': 'Ring', 'subcategories': ['Engagement', 'Wedding', 'Fashion']},
        {'main_class': 'Earring', 'subcategories': ['Stud', 'Hoop', 'Drop']},
        {'main_class': 'Wristwatch', 'subcategories': ['Analog', 'Digital', 'Smart']},
    ])
    proxies: List[str] = field(default_factory=lambda: [
        # Add your proxy addresses here in the format "http://ip:port"
        "http://123.456.789.0:8080",
        "http://234.567.890.1:8080",
        "http://345.678.901.2:8080",
        # Add more proxies as needed
    ])
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36",
        # Add more user agents as needed
    ])
    
    def to_dict(self) -> Dict:
        """
        Convert the ScraperConfig dataclass to a dictionary.
        """
        return {
            "output_dir": self.output_dir,
            "max_items": self.max_items,
            "max_pages": self.max_pages,
            "categories": self.categories,
            "proxies": self.proxies,
            "user_agents": self.user_agents
        }
    
    @staticmethod
    def from_dict(data: Dict):
        """
        Create a ScraperConfig instance from a dictionary.
        """
        return ScraperConfig(
            output_dir=data.get("output_dir", "jewelry_dataset"),
            max_items=int(data.get("max_items", 100)),
            max_pages=int(data.get("max_pages", 5)),
            categories=data.get("categories", [
                {'main_class': 'Necklace', 'subcategories': ['Choker', 'Pendant', 'Chain']},
                {'main_class': 'Pendant', 'subcategories': ['Heart', 'Cross', 'Star']},
                {'main_class': 'Bracelet', 'subcategories': ['Tennis', 'Charm', 'Bangle']},
                {'main_class': 'Ring', 'subcategories': ['Engagement', 'Wedding', 'Fashion']},
                {'main_class': 'Earring', 'subcategories': ['Stud', 'Hoop', 'Drop']},
                {'main_class': 'Wristwatch', 'subcategories': ['Analog', 'Digital', 'Smart']},
            ]),
            proxies=data.get("proxies", [
                "http://123.456.789.0:8080",
                "http://234.567.890.1:8080",
                "http://345.678.901.2:8080",
            ]),
            user_agents=data.get("user_agents", [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/90.0.4430.93 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/14.0.3 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/90.0.4430.93 Safari/537.36",
            ])
        )

# Example usage:
# To load configuration from a JSON file
# with open('config.json', 'r') as f:
#     config_data = json.load(f)
# scraper_config = ScraperConfig.from_dict(config_data)
