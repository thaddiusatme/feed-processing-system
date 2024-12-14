"""Base queue implementation for feed processing."""

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from feed_processor.metrics.prometheus import metrics


class Priority(Enum):
    """Priority levels for queue items.

    Defines three priority levels for feed items:
    - LOW (0): Default priority for older items
    - NORMAL (1): Standard priority for recent items
    - HIGH (2): Urgent items like breaking news
    """

    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class QueueItem:
    """Represents an item in the priority queue.

    Attributes:
        id (str): Unique identifier for the item
        priority (Priority): Item's priority level
        content (Dict[str, Any]): The actual item data
        timestamp (datetime): When the item was added to queue
    """

    id: str
    priority: Priority
    content: Dict[str, Any]
    timestamp: datetime = datetime.now(timezone.utc)


class BaseQueue:
    """Thread-safe priority queue implementation using multiple deques.

    This queue maintains separate deques for each priority level (HIGH, NORMAL, LOW)
    and provides thread-safe operations for adding and removing items. When the queue
    is full, high-priority items can displace lower priority items.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize the queue.

        Args:
            max_size: Maximum number of items across all priority levels
        """
        self.max_size = max_size
        self.queues = {
            Priority.HIGH: deque(),
            Priority.NORMAL: deque(),
            Priority.LOW: deque(),
        }
        self.lock = threading.Lock()

        # Initialize metrics
        self.queue_size = metrics.register_gauge(
            "queue_size_total", "Total number of items in queue", ["priority"]
        )
        self.queue_operations = metrics.register_counter(
            "queue_operations_total", "Total number of queue operations", ["operation"]
        )
        self.queue_latency = metrics.register_histogram(
            "queue_operation_duration_seconds", "Duration of queue operations"
        )

    def size(self) -> int:
        """Get total number of items in queue.

        Returns:
            Total number of items across all priority levels
        """
        with self.lock:
            total = sum(len(q) for q in self.queues.values())
            for priority in Priority:
                self.queue_size.labels(priority=priority.name.lower()).set(
                    len(self.queues[priority])
                )
            return total

    def is_full(self) -> bool:
        """Check if queue is at max capacity.

        Returns:
            True if total items >= max_size
        """
        return self.size() >= self.max_size

    def add(self, item: QueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: QueueItem to add

        Returns:
            True if item was added successfully
        """
        start_time = datetime.now(timezone.utc)
        try:
            with self.lock:
                # If queue is full, try to make room by removing lowest priority items
                if self.is_full():
                    if not self._make_room(item.priority):
                        self.queue_operations.labels(operation="add_failed").inc()
                        return False

                self.queues[item.priority].append(item)
                self.queue_operations.labels(operation="add_success").inc()
                return True

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.queue_latency.observe(duration)

    def get(self, count: int = 1) -> List[QueueItem]:
        """Get items from queue in priority order.

        Args:
            count: Maximum number of items to get

        Returns:
            List of QueueItems in priority order
        """
        start_time = datetime.now(timezone.utc)
        try:
            with self.lock:
                items = []
                remaining = count

                # Get items in priority order
                for priority in reversed(list(Priority)):
                    while remaining > 0 and self.queues[priority]:
                        items.append(self.queues[priority].popleft())
                        remaining -= 1

                self.queue_operations.labels(operation="get").inc(len(items))
                return items

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.queue_latency.observe(duration)

    def peek(self) -> Optional[QueueItem]:
        """Peek at highest priority item without removing it.

        Returns:
            Highest priority QueueItem or None if queue is empty
        """
        with self.lock:
            for priority in reversed(list(Priority)):
                if self.queues[priority]:
                    return self.queues[priority][0]
            return None

    def remove(self, item_id: str) -> bool:
        """Remove a specific item from the queue.

        Args:
            item_id: ID of item to remove

        Returns:
            True if item was found and removed
        """
        start_time = datetime.now(timezone.utc)
        try:
            with self.lock:
                for priority in Priority:
                    queue = self.queues[priority]
                    for i, item in enumerate(queue):
                        if item.id == item_id:
                            del queue[i]
                            self.queue_operations.labels(operation="remove").inc()
                            return True
                return False

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.queue_latency.observe(duration)

    def clear(self) -> None:
        """Clear all items from the queue."""
        with self.lock:
            for queue in self.queues.values():
                queue.clear()
            self.queue_operations.labels(operation="clear").inc()

    def _make_room(self, new_priority: Priority) -> bool:
        """Try to make room for a new item by removing lower priority items.

        Args:
            new_priority: Priority of item we want to add

        Returns:
            True if room was made or already available
        """
        if not self.is_full():
            return True

        # Only remove items of lower priority
        for priority in Priority:
            if priority.value >= new_priority.value:
                continue

            if self.queues[priority]:
                self.queues[priority].pop()
                self.queue_operations.labels(operation="evict").inc()
                return True

        return False
