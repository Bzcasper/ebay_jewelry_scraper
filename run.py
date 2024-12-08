# run.py

from pathlib import Path
import click
from flask import Flask
from scraper.config import ScraperConfig
from scraper.monitoring import ScraperMonitor
from scraper.scheduler import TaskScheduler
import logging
import os

def create_app(config_path: str = None):
    """Create and configure the Flask application."""
    # Initialize base app
    app = Flask(__name__)
    
    # Ensure required directories exist
    for directory in ['jewelry_dataset', 'logs', 'config', 'temp']:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    config = ScraperConfig(config_path)
    app.config.update(config.config)
    
    # Initialize components
    monitor = ScraperMonitor(config.config)
    scheduler = TaskScheduler(config.config)
    
    # Attach to app context
    app.config['monitor'] = monitor
    app.config['scheduler'] = scheduler
    app.config['scraper_config'] = config
    
    # Register blueprints
    from views.main import main_bp
    from views.api import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app

@click.group()
def cli():
    """Jewelry Dataset Creator CLI"""
    pass

@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--config', default=None, help='Path to config file')
def run(host, port, config):
    """Run the web interface"""
    app = create_app(config)
    app.run(host=host, port=port)

@cli.command()
@click.argument('category')
@click.option('--max-items', default=100, help='Maximum items to scrape')
def scrape(category, max_items):
    """Run scraping for a specific category"""
    app = create_app()
    with app.app_context():
        scheduler = app.config['scheduler']
        scheduler.schedule_scraping_task(
            categories=[{'main_category': category, 'subcategories': ['all']}],
            schedule_type='immediate'
        )

@cli.command()
def create_datasets():
    """Create ML datasets from scraped data"""
    app = create_app()
    with app.app_context():
        scheduler = app.config['scheduler']
        scheduler.schedule_dataset_creation(
            source_dir='jewelry_dataset/raw_data',
            schedule_type='immediate'
        )

if __name__ == '__main__':
    cli()