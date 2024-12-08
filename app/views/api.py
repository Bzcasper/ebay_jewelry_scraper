# app/views/api.py

from flask import Blueprint, request, jsonify, current_app
import json
from pathlib import Path

api_bp = Blueprint('api', __name__)

@api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all configured categories."""
    config = current_app.config['scraper_config']
    return jsonify(config.get_categories())

@api_bp.route('/categories', methods=['POST'])
def update_categories():
    """Add or update category."""
    config = current_app.config['scraper_config']
    data = request.json
    
    try:
        if 'main_category' in data:
            if 'subcategory' in data:
                # Add subcategory
                config.update_category(
                    data['main_category'],
                    subcategory=data['subcategory']
                )
            else:
                # Add main category
                config.update_category(
                    data['main_category'],
                    subcategories=[]
                )
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@api_bp.route('/scrape', methods=['POST'])
def start_scraping():
    """Start scraping task."""
    scheduler = current_app.config['scheduler']
    monitor = current_app.config['monitor']
    
    data = request.json
    categories = data.get('categories', [])
    
    if not categories:
        return jsonify({'status': 'error', 'message': 'No categories selected'}), 400
    
    try:
        task_id = scheduler.schedule_scraping_task(
            categories=categories,
            schedule_type='immediate'
        )
        
        return jsonify({
            'status': 'success',
            'task_id': task_id
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/task/<task_id>')
def get_task_status(task_id):
    """Get status of a task."""
    scheduler = current_app.config['scheduler']
    status = scheduler.get_task_status(task_id)
    
    if status:
        return jsonify(status)
    return jsonify({'status': 'not_found'}), 404

@api_bp.route('/create-datasets', methods=['POST'])
def create_datasets():
    """Start dataset creation task."""
    scheduler = current_app.config['scheduler']
    
    try:
        task_id = scheduler.schedule_dataset_creation(
            source_dir='jewelry_dataset/raw_data',
            schedule_type='immediate'
        )
        
        return jsonify({
            'status': 'success',
            'task_id': task_id
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/stats')
def get_stats():
    """Get current system statistics."""
    monitor = current_app.config['monitor']
    return jsonify(monitor.get_performance_stats())

@api_bp.route('/download/dataset/<dataset_type>')
def download_dataset(dataset_type):
    """Download a dataset."""
    if dataset_type not in ['resnet', 'llava']:
        return jsonify({'status': 'error', 'message': 'Invalid dataset type'}), 400
        
    try:
        dataset_path = Path(f'jewelry_dataset/datasets/{dataset_type}')
        if not dataset_path.exists():
            return jsonify({'status': 'error', 'message': 'Dataset not found'}), 404
            
        # Create zip file
        import zipfile
        import io
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in dataset_path.rglob('*'):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(dataset_path))
        
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{dataset_type}_dataset.zip'
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500