"""Content queue for managing feed items."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .metrics import ITEMS_ADDED, ITEMS_REMOVED, QUEUE_OVERFLOWS, QUEUE_SIZE
from .metrics.prometheus import metrics


@dataclass
class QueueItem:
    """Represents an item in the content queue."""

    id: str
    content: Dict[str, Any]
    timestamp: datetime
    priority: int = 0
    retries: int = 0
    max_retries: int = 3


class ContentQueue:
    """Queue for managing content items with metrics tracking."""

    def __init__(self, max_size: Optional[int] = None):
        """Initialize the content queue.

        Args:
            max_size: Optional maximum queue size
        """
        self.items: List[QueueItem] = []
        self.max_size = max_size

        # Initialize metrics using predefined metrics
        self.queue_size = metrics.register_gauge(QUEUE_SIZE.name, QUEUE_SIZE.description)
        self.queue_overflows = metrics.register_counter(
            QUEUE_OVERFLOWS.name, QUEUE_OVERFLOWS.description
        )
        self.items_added = metrics.register_counter(ITEMS_ADDED.name, ITEMS_ADDED.description)
        self.items_removed = metrics.register_counter(ITEMS_REMOVED.name, ITEMS_REMOVED.description)

    def add(self, item: QueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: QueueItem to add

        Returns:
            bool: True if item was added successfully
        """
        if self.max_size and len(self.items) >= self.max_size:
            self.queue_overflows.inc()
            return False

        self.items.append(item)
        self.queue_size.set(len(self.items))
        self.items_added.inc()
        return True

    def remove(self, item_id: str) -> Optional[QueueItem]:
        """Remove and return an item from the queue.

        Args:
            item_id: ID of item to remove

        Returns:
            Optional[QueueItem]: Removed item or None if not found
        """
        for i, item in enumerate(self.items):
            if item.id == item_id:
                removed = self.items.pop(i)
                self.queue_size.set(len(self.items))
                self.items_removed.inc()
                return removed
        return None

    def get(self, item_id: str) -> Optional[QueueItem]:
        """Get an item from the queue without removing it.

        Args:
            item_id: ID of item to get

        Returns:
            Optional[QueueItem]: Item or None if not found
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def clear(self):
        """Clear all items from the queue."""
        items_count = len(self.items)
        self.items = []
        self.queue_size.set(0)
        self.items_removed.inc(items_count)

    def __len__(self) -> int:
        """Return the number of items in the queue."""
        return len(self.items)

    def __bool__(self) -> bool:
        """Return True if queue has items."""
        return bool(self.items)
