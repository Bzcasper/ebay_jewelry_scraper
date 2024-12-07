# scraper/logger.py

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import json
from typing import Optional

class CustomFormatter(logging.Formatter):
    """Custom formatter with color-coding for console output."""
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[94m',    # Blue
        'INFO': '\033[92m',     # Green
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[95m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def __init__(self, use_colors: bool = True):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.use_colors = use_colors

    def format(self, record):
        # Save original values
        original_msg = record.msg
        original_levelname = record.levelname

        if self.use_colors:
            # Add color to level name
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"

        # Format the message
        result = super().format(record)

        # Restore original values
        record.msg = original_msg
        record.levelname = original_levelname

        return result

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging to file."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': str(record.exc_info[0].__name__),
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
            
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra
            
        return json.dumps(log_data)

def setup_logging(
    log_dir: Optional[str] = None,
    log_level: int = logging.INFO,
    use_json: bool = True,
    use_console_colors: bool = True,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Set up logging configuration for the scraping pipeline.
    
    Args:
        log_dir: Directory for log files. If None, uses 'logs' in current directory
        log_level: Minimum log level to capture
        use_json: Whether to use JSON formatting for file logs
        use_console_colors: Whether to use colors in console output
        max_file_size: Maximum size of each log file in bytes
        backup_count: Number of backup log files to keep
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set up log directory
    if log_dir is None:
        log_dir = Path('logs')
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Console handler with color formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(CustomFormatter(use_colors=use_console_colors))
    logger.addHandler(console_handler)

    # File handlers
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Regular log file with rotation by size
    main_log_file = log_dir / f'scraper_{current_time}.log'
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    
    if use_json:
        file_handler.setFormatter(JsonFormatter())
    else:
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    logger.addHandler(file_handler)

    # Daily rotating error log file
    error_log_file = log_dir / f'errors_{current_time}.log'
    error_handler = TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    if use_json:
        error_handler.setFormatter(JsonFormatter())
    else:
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
            'Module: %(module)s\n'
            'Function: %(funcName)s\n'
            'Line: %(lineno)d\n'
            'Message: %(message)s\n'
            '%(exc_info)s\n'
        ))
    logger.addHandler(error_handler)

    # Log initial setup information
    logger.info("Logging system initialized")
    logger.info(f"Log files directory: {log_dir.absolute()}")
    logger.info(f"Main log file: {main_log_file.name}")
    logger.info(f"Error log file: {error_log_file.name}")

class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context to log messages."""
    
    def process(self, msg, kwargs):
        # Add extra context if available
        extra = kwargs.get('extra', {})
        if self.extra:
            extra.update(self.extra)
            kwargs['extra'] = extra
        
        return msg, kwargs

def get_logger(name: str, **kwargs) -> LoggerAdapter:
    """
    Get a logger instance with optional extra context.
    
    Args:
        name: Logger name
        **kwargs: Extra context to add to all log messages
        
    Returns:
        LoggerAdapter: Configured logger adapter
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, kwargs)

# Example usage:
"""
# Basic setup
setup_logging()

# Get logger for specific module
logger = get_logger(__name__, component='scraper', category='necklaces')

# Usage
logger.info("Starting scrape process")
logger.error("Failed to download image", extra={'url': 'http://example.com/image.jpg'})

try:
    # Some code that might fail
    raise ValueError("Example error")
except Exception as e:
    logger.exception("An error occurred during scraping")
"""