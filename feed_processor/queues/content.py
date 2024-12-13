from typing import Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import json
import hashlib
from feed_processor.queues.base import PriorityQueue

@dataclass
class QueuedContent:
    """Represents a content item with processing metadata."""
    content_id: str
    content: Dict[str, Any]
    timestamp: datetime = datetime.now()
    retry_count: int = 0
    processing_status: str = "pending"
    content_hash: str = ""

class QueueItem:
    """Represents an item in the content queue."""
    def __init__(self, content: Dict[str, Any], priority: int = 0):
        self.content = content
        self.priority = priority
        self.retry_count = 0
        self.next_retry: Optional[datetime] = None

class ContentQueue:
    """
    Queue for managing feed content processing with duplicate detection
    and retry management.
    """
    def __init__(self, max_size: int = 1000, dedup_window: Optional[int] = None, deduplication_window: Optional[int] = None):
        self.max_size = max_size
        self.deduplication_window = deduplication_window or dedup_window or 3600
        self.items: list[QueueItem] = []
        self.processed_ids: Set[str] = set()
        self.lock = threading.Lock()
        
    def _generate_content_hash(self, content: Dict[str, Any]) -> str:
        """Generate a stable hash for content to detect duplicates"""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _clean_old_hashes(self) -> None:
        """Remove hashes older than dedup_window"""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=self.deduplication_window)
        self.processed_ids = {
            h for h in self.processed_ids
            if h > cutoff_time
        }
    
    def is_duplicate(self, content: Dict[str, Any]) -> bool:
        """Check if content is a duplicate within the dedup window"""
        content_hash = self._generate_content_hash(content)
        self._clean_old_hashes()
        return content_hash in self.processed_ids
    
    def enqueue(self, content: Dict[str, Any]) -> Optional[QueuedContent]:
        """Add an item to the queue if it hasn't been processed recently."""
        with self.lock:
            if len(self.items) >= self.max_size:
                return None
                
            content_id = str(content.get('id', ''))
            if content_id in self.processed_ids:
                return None
                
            item = QueueItem(content)
            self.items.append(item)
            self.processed_ids.add(content_id)
            return QueuedContent(content_id, content)
            
    def dequeue(self) -> Optional[QueueItem]:
        """Remove and return the next item from the queue."""
        with self.lock:
            if not self.items:
                return None
                
            now = datetime.now()
            ready_items = [
                item for item in self.items
                if not item.next_retry or item.next_retry <= now
            ]
            
            if not ready_items:
                return None
                
            # Get highest priority item
            item = max(ready_items, key=lambda x: x.priority)
            self.items.remove(item)
            return item
            
    def requeue(self, item: QueueItem, delay: float) -> None:
        """Put an item back in the queue with a delay."""
        item.retry_count += 1
        item.next_retry = datetime.now() + timedelta(seconds=delay)
        
        with self.lock:
            self.items.append(item)
            
    @property
    def size(self) -> int:
        """Get the current size of the queue."""
        with self.lock:
            return len(self.items)
            
    def clear(self) -> None:
        """Clear all items from the queue."""
        with self.lock:
            self.items.clear()
            self.processed_ids.clear()
            
    def mark_processed(self, content: QueueItem) -> None:
        """Mark content as successfully processed"""
        content.processing_status = "processed"
    
    def mark_failed(self, content: QueueItem, max_retries: int = 3) -> bool:
        """
        Mark content as failed and requeue if retries available
        Returns True if requeued, False if max retries exceeded
        """
        content.retry_count += 1
        if content.retry_count <= max_retries:
            content.processing_status = "retry"
            self.requeue(content, 60)
            return True
        content.processing_status = "failed"
        return False
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.size
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queue_size": self.size,
            "unique_contents": len(self.processed_ids),
            "oldest_item_age": (
                (datetime.now() - self.items[0].timestamp).total_seconds()
                if self.items else 0
            )
        }
