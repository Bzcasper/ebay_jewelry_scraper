# scraper/logger.py
import logging
import os

def setup_logging(log_file: str = "scraper.log"):
    """
    Set up logging configurations.
    
    Args:
        log_file (str): Path to the log file.
    """
    log_path = os.path.join(os.getcwd(), log_file)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
