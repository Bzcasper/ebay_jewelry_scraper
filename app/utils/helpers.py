# app/utils/helpers.py

import os
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime
import hashlib

def ensure_directories(*paths: str) -> None:
    """Ensure directories exist."""
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)

def get_file_hash(filepath: Path) -> str:
    """Get SHA256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def format_size(size_bytes: int) -> str:
    """Format file size to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def get_directory_stats(directory: Path) -> Dict:
    """Get statistics about directory contents."""
    stats = {
        'total_files': 0,
        'total_size': 0,
        'file_types': {},
        'last_modified': None
    }
    
    if not directory.exists():
        return stats
    
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            stats['total_files'] += 1
            size = file_path.stat().st_size
            stats['total_size'] += size
            
            # Track file types
            ext = file_path.suffix.lower()
            if ext in stats['file_types']:
                stats['file_types'][ext] += 1
            else:
                stats['file_types'][ext] = 1
            
            # Track last modified
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if not stats['last_modified'] or mtime > stats['last_modified']:
                stats['last_modified'] = mtime
    
    return stats

def validate_category(category: str, subcategory: Optional[str] = None) -> bool:
    """Validate category and subcategory."""
    valid_categories = {
        'necklace': ['choker', 'pendant', 'chain'],
        'pendant': ['heart', 'cross', 'star'],
        'bracelet': ['tennis', 'charm', 'bangle'],
        'ring': ['engagement', 'wedding', 'fashion'],
        'earring': ['stud', 'hoop', 'drop'],
        'wristwatch': ['analog', 'digital', 'smart']
    }
    
    if category.lower() not in valid_categories:
        return False
        
    if subcategory and subcategory.lower() not in valid_categories[category.lower()]:
        return False
        
    return True

def save_task_result(task_id: str, result: Dict) -> None:
    """Save task result to file."""
    results_dir = Path('logs/task_results')
    results_dir.mkdir(parents=True, exist_ok=True)
    
    result_path = results_dir / f"{task_id}.json"
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)

def load_task_result(task_id: str) -> Optional[Dict]:
    """Load task result from file."""
    result_path = Path(f'logs/task_results/{task_id}.json')
    if result_path.exists():
        with open(result_path) as f:
            return json.load(f)
    return None

def clean_old_files(directory: Path, max_age_days: int = 7) -> int:
    """Clean files older than max_age_days."""
    if not directory.exists():
        return 0
        
    cleaned = 0
    cutoff = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
    
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff:
            file_path.unlink()
            cleaned += 1
            
    return cleaned