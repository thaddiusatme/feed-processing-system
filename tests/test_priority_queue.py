import pytest
from datetime import datetime, timezone
from feed_processor.priority_queue import PriorityQueue, Priority, QueueItem

class TestPriorityQueue:
    def test_queue_initialization(self):
        queue = PriorityQueue(max_size=5)
        assert queue.size == 0
        assert queue.max_size == 5
        assert queue.is_empty()
        assert not queue.is_full()

    def test_enqueue_basic(self):
        queue = PriorityQueue(max_size=5)
        item = QueueItem("1", Priority.NORMAL, {"data": "test"}, datetime.now(timezone.utc))
        assert queue.enqueue(item)
        assert queue.size == 1
        assert not queue.is_empty()

    def test_dequeue_basic(self):
        queue = PriorityQueue(max_size=5)
        item = QueueItem("1", Priority.NORMAL, {"data": "test"}, datetime.now(timezone.utc))
        queue.enqueue(item)
        dequeued = queue.dequeue()
        assert dequeued == item
        assert queue.size == 0

    def test_priority_ordering(self):
        queue = PriorityQueue(max_size=5)
        low = QueueItem("1", Priority.LOW, {"data": "low"}, datetime.now(timezone.utc))
        normal = QueueItem("2", Priority.NORMAL, {"data": "normal"}, datetime.now(timezone.utc))
        high = QueueItem("3", Priority.HIGH, {"data": "high"}, datetime.now(timezone.utc))
        
        queue.enqueue(low)
        queue.enqueue(normal)
        queue.enqueue(high)
        
        assert queue.dequeue() == high
        assert queue.dequeue() == normal
        assert queue.dequeue() == low

    def test_full_queue_behavior(self):
        queue = PriorityQueue(max_size=2)
        item1 = QueueItem("1", Priority.LOW, {"data": "test1"}, datetime.now(timezone.utc))
        item2 = QueueItem("2", Priority.LOW, {"data": "test2"}, datetime.now(timezone.utc))
        item3 = QueueItem("3", Priority.HIGH, {"data": "test3"}, datetime.now(timezone.utc))
        
        assert queue.enqueue(item1)
        assert queue.enqueue(item2)
        assert queue.is_full()
        assert queue.enqueue(item3)  # Should succeed by removing oldest low priority item
        
        dequeued = queue.dequeue()
        assert dequeued == item3
