import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

from feed_processor.queues.base import BaseQueue, Priority


@dataclass
class QueuedContent:
    """Represents a content item with processing metadata."""

    content_id: str
    content: Dict[str, Any]
    timestamp: datetime = datetime.now()
    retry_count: int = 0
    processing_status: str = "pending"
    content_hash: str = ""


class ContentQueue(BaseQueue):
    """Queue for managing feed content processing with duplicate detection
    and retry management.
    """

    def __init__(
        self,
        max_size: int = 1000,
        dedup_window: Optional[int] = None,
        deduplication_window: Optional[int] = None,
    ):
        """Initialize content queue.

        Args:
            max_size: Maximum number of items in queue
            dedup_window: Deprecated, use deduplication_window
            deduplication_window: Time window in seconds for deduplication
        """
        super().__init__(max_size)
        self.deduplication_window = deduplication_window or dedup_window or 3600
        self.processed_hashes: Dict[str, datetime] = {}
        self.lock = threading.Lock()

    def _generate_content_hash(self, content: Dict[str, Any]) -> str:
        """Generate a stable hash for content to detect duplicates.

        Args:
            content: Content to hash

        Returns:
            Stable hash of content
        """
        # Sort keys to ensure stable hash
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _clean_old_hashes(self) -> None:
        """Remove hashes older than dedup_window."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.deduplication_window)

        # Remove old hashes
        old_hashes = [h for h, ts in self.processed_hashes.items() if ts < cutoff]
        for h in old_hashes:
            del self.processed_hashes[h]

    def is_duplicate(self, content: Dict[str, Any]) -> bool:
        """Check if content is a duplicate within the dedup window.

        Args:
            content: Content to check

        Returns:
            True if content is a duplicate
        """
        with self.lock:
            self._clean_old_hashes()
            content_hash = self._generate_content_hash(content)
            return content_hash in self.processed_hashes

    def enqueue(self, content: Dict[str, Any], priority: Priority = Priority.NORMAL) -> bool:
        """Add an item to the queue if it hasn't been processed recently.

        Args:
            content: Content to enqueue
            priority: Priority level for the content

        Returns:
            True if content was enqueued, False if duplicate or queue full
        """
        with self.lock:
            if self.is_duplicate(content):
                return False

            content_hash = self._generate_content_hash(content)
            queued_content = QueuedContent(
                content_id=content.get("id", ""),
                content=content,
                content_hash=content_hash,
            )

            if super().enqueue(queued_content, priority):
                self.processed_hashes[content_hash] = datetime.now()
                return True
            return False

    def dequeue(self) -> Optional[QueuedContent]:
        """Remove and return the next item from the queue.

        Returns:
            Next item by priority, or None if queue empty
        """
        return super().dequeue()

    def mark_processed(self, content: QueuedContent) -> None:
        """Mark content as successfully processed.

        Args:
            content: Content that was processed
        """
        with self.lock:
            self.processed_hashes[content.content_hash] = datetime.now()

    def mark_failed(self, content: QueuedContent, max_retries: int = 3) -> bool:
        """Mark content as failed and requeue if retries available.

        Args:
            content: Content that failed
            max_retries: Maximum retry attempts

        Returns:
            True if requeued, False if max retries exceeded
        """
        content.retry_count += 1
        if content.retry_count <= max_retries:
            # Use exponential backoff for retries
            delay = 2**content.retry_count
            content.processing_status = "retrying"
            return self.enqueue(
                content.content,
                Priority.LOW,
            )

        content.processing_status = "failed"
        return False

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        with self.lock:
            return {
                "size": self.size,
                "max_size": self.max_size,
                "dedup_window": self.deduplication_window,
                "processed_hashes": len(self.processed_hashes),
            }
