"""Content queue module for managing feed items."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from .metrics.metrics import ITEMS_ADDED, ITEMS_REMOVED, QUEUE_OVERFLOWS, QUEUE_SIZE

logger = structlog.get_logger(__name__)


@dataclass
class QueueItem:
    """Represents an item in the content queue."""

    id: str
    content: Dict[str, Any]
    timestamp: float


class ContentQueue:
    """A queue for managing feed content items."""

    def __init__(self, max_size: int = 1000):
        """Initialize the content queue.

        Args:
            max_size: Maximum number of items allowed in the queue
        """
        self.max_size = max_size
        self._queue = asyncio.Queue(maxsize=max_size)
        self._size = 0

    async def add(self, item: QueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: Item to add to the queue

        Returns:
            bool: True if item was added successfully
        """
        try:
            if self._size >= self.max_size:
                QUEUE_OVERFLOWS.inc()
                logger.warning(
                    "Queue overflow",
                    queue_size=self._size,
                    max_size=self.max_size,
                    item_id=item.id,
                )
                return False

            await self._queue.put(item)
            self._size += 1
            ITEMS_ADDED.inc()
            QUEUE_SIZE.set(self._size)
            logger.debug("Item added to queue", item_id=item.id, queue_size=self._size)
            return True

        except Exception as e:
            logger.error("Error adding item to queue", error=str(e), item_id=item.id)
            return False

    async def get(self) -> Optional[QueueItem]:
        """Get the next item from the queue.

        Returns:
            Optional[QueueItem]: Next item from the queue or None if queue is empty
        """
        try:
            item = await self._queue.get()
            self._size -= 1
            ITEMS_REMOVED.inc()
            QUEUE_SIZE.set(self._size)
            logger.debug("Item removed from queue", item_id=item.id, queue_size=self._size)
            return item

        except asyncio.QueueEmpty:
            return None
        except Exception as e:
            logger.error("Error getting item from queue", error=str(e))
            return None

    def clear(self):
        """Clear all items from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._size -= 1
                ITEMS_REMOVED.inc()
            except asyncio.QueueEmpty:
                break

        self._size = 0
        QUEUE_SIZE.set(0)
        logger.info("Queue cleared")

    def empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            bool: True if the queue is empty
        """
        return self._queue.empty()

    def qsize(self) -> int:
        """Get the current size of the queue.

        Returns:
            int: Current size of the queue
        """
        return self._size

    @property
    def size(self) -> int:
        """Get the current size of the queue.

        Returns:
            int: Current queue size
        """
        return self._size

    def __len__(self) -> int:
        """Get the current size of the queue.

        Returns:
            int: Current queue size
        """
        return self._size
