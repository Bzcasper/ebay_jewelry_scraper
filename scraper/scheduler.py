# scraper/scheduler.py

import schedule
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import json
from threading import Thread, Event
import queue
import traceback

class TaskScheduler:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.task_queue = queue.Queue()
        self.stop_event = Event()
        self.active_tasks = {}
        self.task_history = []
        
        # Create task history directory
        self.history_dir = Path('logs/task_history')
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize worker thread
        self.worker_thread = Thread(target=self._process_task_queue, daemon=True)
        self.worker_thread.start()

    def schedule_scraping_task(self, categories: List[Dict], 
                             schedule_type: str = 'daily', 
                             time: str = '00:00') -> str:
        """Schedule a new scraping task."""
        task_id = f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        task = {
            'id': task_id,
            'type': 'scraping',
            'categories': categories,
            'schedule_type': schedule_type,
            'schedule_time': time,
            'status': 'scheduled',
            'created_at': datetime.now().isoformat()
        }
        
        # Add to schedule based on schedule_type
        if schedule_type == 'daily':
            schedule.every().day.at(time).do(
                self._queue_task, task
            ).tag(task_id)
        elif schedule_type == 'weekly':
            schedule.every().week.at(time).do(
                self._queue_task, task
            ).tag(task_id)
        elif schedule_type == 'immediate':
            self._queue_task(task)
            
        self.active_tasks[task_id] = task
        self._save_task_history()
        
        return task_id

    def schedule_dataset_creation(self, source_dir: str,
                                schedule_type: str = 'immediate') -> str:
        """Schedule dataset creation task."""
        task_id = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        task = {
            'id': task_id,
            'type': 'dataset_creation',
            'source_dir': source_dir,
            'schedule_type': schedule_type,
            'status': 'scheduled',
            'created_at': datetime.now().isoformat()
        }
        
        if schedule_type == 'immediate':
            self._queue_task(task)
        
        self.active_tasks[task_id] = task
        self._save_task_history()
        
        return task_id

    def _queue_task(self, task: Dict) -> None:
        """Add task to processing queue."""
        self.task_queue.put(task)
        task['status'] = 'queued'
        self._save_task_history()

    def _process_task_queue(self) -> None:
        """Process tasks from queue."""
        while not self.stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                self._execute_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing task queue: {e}")
                continue

    def _execute_task(self, task: Dict) -> None:
        """Execute a scheduled task."""
        try:
            task['status'] = 'running'
            task['started_at'] = datetime.now().isoformat()
            self._save_task_history()
            
            if task['type'] == 'scraping':
                self._run_scraping_task(task)
            elif task['type'] == 'dataset_creation':
                self._run_dataset_creation(task)
                
            task['status'] = 'completed'
            task['completed_at'] = datetime.now().isoformat()
            
        except Exception as e:
            task['status'] = 'failed'
            task['error'] = str(e)
            task['traceback'] = traceback.format_exc()
            self.logger.error(f"Task {task['id']} failed: {e}")
            
        finally:
            self._save_task_history()

    def _run_scraping_task(self, task: Dict) -> None:
        """Run scraping task with progress tracking."""
        from scraper.core import EbayJewelryScraper
        
        scraper = EbayJewelryScraper(self.config)
        total_items = 0
        
        for category in task['categories']:
            try:
                items = scraper.scrape_category(
                    category['main_category'],
                    category['subcategories']
                )
                total_items += len(items)
                
                task['progress'] = {
                    'current_category': category['main_category'],
                    'items_scraped': total_items,
                    'last_update': datetime.now().isoformat()
                }
                self._save_task_history()
                
            except Exception as e:
                self.logger.error(
                    f"Error scraping category {category['main_category']}: {e}"
                )
                continue
        
        task['total_items_scraped'] = total_items

    def _run_dataset_creation(self, task: Dict) -> None:
        """Run dataset creation task."""
        from scraper.dataset_creator import JewelryDatasetCreator
        
        creator = JewelryDatasetCreator(self.config)
        
        # Create datasets
        resnet_stats, llava_stats = creator.create_datasets(
            Path(task['source_dir'])
        )
        
        task['dataset_stats'] = {
            'resnet': resnet_stats,
            'llava': llava_stats
        }

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a task."""
        return self.active_tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task['status'] in ['scheduled', 'queued']:
                schedule.clear(task_id)
                task['status'] = 'cancelled'
                self._save_task_history()
                return True
        return False

    def _save_task_history(self) -> None:
        """Save task history to file."""
        history_file = self.history_dir / 'task_history.json'
        try:
            history = {
                'last_updated': datetime.now().isoformat(),
                'active_tasks': self.active_tasks,
                'task_history': self.task_history[-100:]  # Keep last 100 tasks
            }
            
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving task history: {e}")

    def cleanup_old_tasks(self, days: int = 7) -> None:
        """Clean up old completed tasks."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cleaned_tasks = {}
        for task_id, task in self.active_tasks.items():
            if task['status'] in ['completed', 'failed', 'cancelled']:
                completed_at = datetime.fromisoformat(task['completed_at'])
                if completed_at > cutoff_date:
                    cleaned_tasks[task_id] = task
            else:
                cleaned_tasks[task_id] = task
                
        self.active_tasks = cleaned_tasks
        self._save_task_history()

    def get_task_statistics(self) -> Dict:
        """Get statistics about tasks."""
        stats = {
            'total_tasks': len(self.active_tasks),
            'status_counts': {
                'scheduled': 0,
                'queued': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0
            },
            'type_counts': {
                'scraping': 0,
                'dataset_creation': 0
            }
        }
        
        for task in self.active_tasks.values():
            stats['status_counts'][task['status']] += 1
            stats['type_counts'][task['type']] += 1
            
        return stats

    def stop(self) -> None:
        """Stop the scheduler."""
        self.stop_event.set()
        schedule.clear()
        self.worker_thread.join()

# Example usage:
if __name__ == '__main__':
    from config import ScraperConfig
    
    # Initialize scheduler
    config = ScraperConfig()
    scheduler = TaskScheduler(config.config)
    
    # Schedule immediate scraping task
    categories = [
        {
            'main_category': 'ring',
            'subcategories': ['Wedding', 'Engagement']
        }
    ]
    
    task_id = scheduler.schedule_scraping_task(
        categories=categories,
        schedule_type='immediate'
    )
    
    # Monitor task
    while True:
        status = scheduler.get_task_status(task_id)
        if status['status'] in ['completed', 'failed']:
            break
        time.sleep(5)
    
    # Cleanup and stop
    scheduler.cleanup_old_tasks()
    scheduler.stop()