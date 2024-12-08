# app/views/main.py

from flask import Blueprint, render_template, current_app, jsonify
from pathlib import Path

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render main page."""
    config = current_app.config['scraper_config']
    monitor = current_app.config['monitor']
    
    # Get current categories
    categories = config.get_categories()
    
    # Get system stats
    stats = monitor.get_performance_stats()
    
    return render_template('index.html', 
                         categories=categories,
                         stats=stats)

@main_bp.route('/dashboard')
def dashboard():
    """Render monitoring dashboard."""
    monitor = current_app.config['monitor']
    stats = monitor.get_performance_stats()
    
    return render_template('dashboard.html', stats=stats)

@main_bp.route('/datasets')
def datasets():
    """Render dataset management page."""
    # Get dataset statistics
    resnet_dir = Path('jewelry_dataset/datasets/resnet')
    llava_dir = Path('jewelry_dataset/datasets/llava')
    
    dataset_stats = {
        'resnet': {
            'total_images': len(list(resnet_dir.rglob('*.jpg'))) if resnet_dir.exists() else 0,
            'size_mb': sum(f.stat().st_size for f in resnet_dir.rglob('*') if f.is_file()) / (1024 * 1024) if resnet_dir.exists() else 0
        },
        'llava': {
            'total_images': len(list(llava_dir.rglob('*.jpg'))) if llava_dir.exists() else 0,
            'size_mb': sum(f.stat().st_size for f in llava_dir.rglob('*') if f.is_file()) / (1024 * 1024) if llava_dir.exists() else 0
        }
    }
    
    return render_template('datasets.html', stats=dataset_stats)