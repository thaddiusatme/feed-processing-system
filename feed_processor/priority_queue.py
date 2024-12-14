"""Priority queue implementation for feed processing."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .metrics import QUEUE_OVERFLOWS, QUEUE_SIZE
from .metrics.prometheus import metrics


class Priority(Enum):
    """Priority levels for queue items."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    URGENT = auto()


@dataclass
class QueueItem:
    """Represents an item in the priority queue."""

    id: str
    content: Dict[str, Any]
    priority: Priority
    timestamp: datetime
    retries: int = 0
    max_retries: int = 3


class PriorityQueue:
    """Priority queue implementation with metrics tracking."""

    def __init__(self, max_size: Optional[int] = None):
        """Initialize the priority queue.

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
        self.items_by_priority = metrics.register_gauge(
            "priority_queue_items_by_priority",
            "Number of items in queue by priority level",
            ["priority"],
        )
        self.items_added = metrics.register_counter(
            "priority_queue_items_added_total",
            "Total number of items added to the queue",
            ["priority"],
        )
        self.items_removed = metrics.register_counter(
            "priority_queue_items_removed_total",
            "Total number of items removed from the queue",
            ["priority"],
        )

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

        # Insert item in priority order
        index = 0
        for i, existing in enumerate(self.items):
            if item.priority.value <= existing.priority.value:
                index = i
                break
            index = i + 1

        self.items.insert(index, item)
        self.queue_size.set(len(self.items))
        self.items_added.labels(priority=item.priority.name.lower()).inc()
        self._update_priority_metrics()
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
                self.items_removed.labels(priority=removed.priority.name.lower()).inc()
                self._update_priority_metrics()
                return removed
        return None

    def get_next(self) -> Optional[QueueItem]:
        """Get the next item from the queue based on priority.

        Returns:
            Optional[QueueItem]: Next item or None if queue is empty
        """
        if not self.items:
            return None

        item = self.items[0]
        self.items = self.items[1:]
        self.queue_size.set(len(self.items))
        self.items_removed.labels(priority=item.priority.name.lower()).inc()
        self._update_priority_metrics()
        return item

    def _update_priority_metrics(self):
        """Update metrics for items by priority."""
        priority_counts = {p: 0 for p in Priority}
        for item in self.items:
            priority_counts[item.priority] += 1

        for priority, count in priority_counts.items():
            self.items_by_priority.labels(priority=priority.name.lower()).set(count)

    def clear(self):
        """Clear all items from the queue."""
        for item in self.items:
            self.items_removed.labels(priority=item.priority.name.lower()).inc()
        self.items = []
        self.queue_size.set(0)
        self._update_priority_metrics()

    def __len__(self) -> int:
        """Return the number of items in the queue."""
        return len(self.items)

    def __bool__(self) -> bool:
        """Return True if queue has items."""
        return bool(self.items)
