import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from feed_processor.metrics.prometheus import MetricsCollector


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
    timestamp: datetime


class PriorityQueue:
    """Thread-safe priority queue implementation using multiple deques.

    This queue maintains separate deques for each priority level (HIGH, NORMAL, LOW)
    and provides thread-safe operations for adding and removing items. When the queue
    is full, high-priority items can displace lower priority items.

    The implementation uses Python's collections.deque for O(1) operations and
    threading.Lock for thread safety.

    Attributes:
        _max_size (int): Maximum total items across all priority levels
        _queues (Dict[Priority, deque]): Separate queue for each priority
        _lock (threading.Lock): Lock for thread-safe operations
        _size (int): Current total number of items
        metrics (MetricsCollector): Metrics collector for queue metrics
    """

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the priority queue.

        Args:
            max_size: Maximum number of items the queue can hold

        Raises:
            ValueError: If max_size is less than 1
        """
        if max_size < 1:
            raise ValueError("Queue size must be at least 1")

        self._max_size = max_size
        self._queues: Dict[Priority, Deque[QueueItem]] = {
            Priority.HIGH: deque(maxlen=max_size),
            Priority.NORMAL: deque(maxlen=max_size),
            Priority.LOW: deque(maxlen=max_size),
        }
        self._lock = threading.Lock()
        self.metrics = MetricsCollector()
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize queue metrics."""
        # Queue size metrics
        self.metrics.set_gauge("queue_size_total", 0)
        self.metrics.set_gauge("queue_size", 0, labels={"priority": "high"})
        self.metrics.set_gauge("queue_size", 0, labels={"priority": "normal"})
        self.metrics.set_gauge("queue_size", 0, labels={"priority": "low"})

        # Operation metrics
        self.metrics.increment("enqueued_items", 0, labels={"priority": "high"})
        self.metrics.increment("enqueued_items", 0, labels={"priority": "normal"})
        self.metrics.increment("enqueued_items", 0, labels={"priority": "low"})
        self.metrics.increment("dequeued_items", 0)

        # Overflow metrics
        self.metrics.increment("queue_overflows", 0, labels={"priority": "high"})
        self.metrics.increment("queue_overflows", 0, labels={"priority": "normal"})
        self.metrics.increment("queue_overflows", 0, labels={"priority": "low"})

    def enqueue(self, item: QueueItem, priority: Priority = Priority.NORMAL) -> bool:
        """Add an item to the appropriate priority queue.

        When queue is full:
        - HIGH priority items can displace LOW or NORMAL items
        - Other priority items are rejected

        Args:
            item: Queue item with priority level

        Returns:
            True if item was added, False if rejected

        Thread Safety:
            This method is thread-safe.

        Note:
            When displacing items, oldest LOW priority items are removed first,
            followed by oldest NORMAL priority items if necessary.
        """
        with self._lock:
            if self._size >= self._max_size:
                if item.priority == Priority.HIGH:
                    # Try to remove a low priority item
                    if len(self._queues[Priority.LOW]) > 0:
                        self._queues[Priority.LOW].popleft()
                        self._size -= 1
                    elif len(self._queues[Priority.NORMAL]) > 0:
                        self._queues[Priority.NORMAL].popleft()
                        self._size -= 1
                    else:
                        self.metrics.increment(
                            "queue_overflows", labels={"priority": item.priority.name.lower()}
                        )
                        return False
                else:
                    self.metrics.increment(
                        "queue_overflows", labels={"priority": item.priority.name.lower()}
                    )
                    return False

            self._queues[item.priority].append(item)
            self.metrics.increment(
                "enqueued_items", labels={"priority": item.priority.name.lower()}
            )
            self._size += 1
            self._update_size_metrics()
            return True

    def dequeue(self) -> Optional[QueueItem]:
        """Remove and return highest priority item available.

        Returns items in priority order (HIGH -> NORMAL -> LOW).
        Within each priority level, oldest items are returned first.

        Returns:
            Next item by priority, or None if queue is empty

        Thread Safety:
            This method is thread-safe.
        """
        with self._lock:
            if self._size == 0:
                return None

            for priority in [Priority.HIGH, Priority.NORMAL, Priority.LOW]:
                if len(self._queues[priority]) > 0:
                    self._size -= 1
                    item = self._queues[priority].popleft()
                    self.metrics.increment("dequeued_items")
                    self._update_size_metrics()
                    return item
            return None

    def _update_size_metrics(self):
        """Update all queue size metrics."""
        total_size = sum(len(q) for q in self._queues.values())
        self.metrics.set_gauge("queue_size_total", total_size)

        for priority, queue in self._queues.items():
            self.metrics.set_gauge(
                "queue_size", len(queue), labels={"priority": priority.name.lower()}
            )

    @property
    def size(self) -> int:
        """Get current total number of items in queue.

        Returns:
            Total items across all priority levels

        Thread Safety:
            This property is thread-safe.
        """
        with self._lock:
            return self._size

    @property
    def max_size(self) -> int:
        """Get maximum queue capacity.

        Returns:
            Maximum number of items allowed
        """
        return self._max_size

    def is_empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if no items in queue, False otherwise

        Thread Safety:
            This method is thread-safe.
        """
        with self._lock:
            return self._size == 0

    def is_full(self) -> bool:
        """Check if queue is at maximum capacity.

        Returns:
            True if queue is full, False otherwise

        Thread Safety:
            This method is thread-safe.
        """
        with self._lock:
            return self._size >= self._max_size

    def peek(self) -> Optional[QueueItem]:
        """View next item without removing it.

        Similar to dequeue() but doesn't modify the queue.
        Returns highest priority item available.

        Returns:
            Next item by priority, or None if queue is empty

        Thread Safety:
            This method is thread-safe.
        """
        with self._lock:
            if self._size == 0:
                return None

            for priority in [Priority.HIGH, Priority.NORMAL, Priority.LOW]:
                if len(self._queues[priority]) > 0:
                    return self._queues[priority][0]

            return None

    def clear(self) -> None:
        """Remove all items from all priority queues.

        Resets the queue to empty state.

        Thread Safety:
            This method is thread-safe.
        """
        with self._lock:
            for priority in Priority:
                self._queues[priority].clear()
            self._size = 0
            self._update_size_metrics()
