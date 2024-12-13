"""Priority Queue implementation for feed processing system.

This module provides a generic priority queue implementation that supports
priority-based ordering of items with timestamps for FIFO behavior within
the same priority level.
"""

import heapq
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Generic, List, Optional, TypeVar


class Priority(IntEnum):
    """Priority levels for queue items."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


T = TypeVar("T")


@dataclass
class QueueItem(Generic[T]):
    """A queue item with priority and timestamp information."""

    priority: Priority
    data: T
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def __lt__(self, other: "QueueItem") -> bool:
        """Compare items based on priority and timestamp."""
        return (self.priority, -self.timestamp) < (other.priority, -other.timestamp)


class PriorityQueue(Generic[T]):
    """A thread-safe priority queue implementation with size limits."""

    def __init__(self, max_size: Optional[int] = None):
        """Initialize the priority queue.

        Args:
            max_size: Maximum number of items the queue can hold.
        """
        self.max_size = max_size
        self._queue: List[QueueItem[T]] = []
        self._size = 0

    def push(
        self,
        item: T,
        priority: Priority = Priority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Push an item onto the priority queue.

        Args:
            item: The item to push onto the queue.
            priority: The priority of the item.
            metadata: Optional metadata for the item.

        Returns:
            True if the item was successfully pushed, False if the queue is full.
        """
        if self.max_size and self._size >= self.max_size:
            if not self._queue or priority <= self._queue[0].priority:
                return False
            heapq.heappop(self._queue)
            self._size -= 1

        queue_item = QueueItem(
            priority=priority, data=item, timestamp=time.time(), metadata=metadata
        )
        heapq.heappush(self._queue, queue_item)
        self._size += 1
        return True

    def pop(self) -> Optional[QueueItem[T]]:
        """Pop the highest-priority item from the queue.

        Returns:
            The highest-priority item, or None if the queue is empty.
        """
        if not self._queue:
            return None
        self._size -= 1
        return heapq.heappop(self._queue)

    def peek(self) -> Optional[QueueItem[T]]:
        """Get the highest-priority item from the queue without removing it.

        Returns:
            The highest-priority item, or None if the queue is empty.
        """
        if not self._queue:
            return None
        return self._queue[0]

    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()
        self._size = 0

    def size(self) -> int:
        """Get the number of items in the queue.

        Returns:
            The number of items in the queue.
        """
        return self._size

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if the queue is empty, False otherwise.
        """
        return self._size == 0

    def is_full(self) -> bool:
        """Check if the queue is full.

        Returns:
            True if the queue is full, False otherwise.
        """
        return self.max_size is not None and self._size >= self.max_size

    def get_items_by_priority(self, priority: Priority) -> List[QueueItem[T]]:
        """Get all items with a given priority.

        Args:
            priority: The priority to filter by.

        Returns:
            A list of items with the given priority.
        """
        return [item for item in self._queue if item.priority == priority]
