import heapq
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QueueItem:
    content_id: str
    content: Dict[str, Any]
    priority: int
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def __lt__(self, other: "QueueItem") -> bool:
        return (self.priority, -self.timestamp) < (other.priority, -other.timestamp)


class ContentQueue:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: List[QueueItem] = []
        self._content_ids: set[str] = set()

    def push(self, item: QueueItem) -> bool:
        if item.content_id in self._content_ids:
            return False

        if len(self._queue) >= self.max_size:
            oldest = heapq.heappop(self._queue)
            self._content_ids.remove(oldest.content_id)

        heapq.heappush(self._queue, item)
        self._content_ids.add(item.content_id)
        return True

    def pop(self) -> Optional[QueueItem]:
        if not self._queue:
            return None

        item = heapq.heappop(self._queue)
        self._content_ids.remove(item.content_id)
        return item

    def peek(self) -> Optional[QueueItem]:
        if not self._queue:
            return None
        return self._queue[0]

    def contains(self, content_id: str) -> bool:
        return content_id in self._content_ids

    def clear(self) -> None:
        self._queue.clear()
        self._content_ids.clear()

    def size(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def is_full(self) -> bool:
        return len(self._queue) >= self.max_size


@dataclass
class QueuedContent:
    content_id: str
    content: Dict[str, Any]
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def to_queue_item(self) -> QueueItem:
        return QueueItem(
            content_id=self.content_id,
            content=self.content,
            priority=self.priority,
            timestamp=time.time(),
            metadata=self.metadata,
        )
