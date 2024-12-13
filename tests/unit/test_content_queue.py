import pytest
from datetime import datetime, timedelta
import time
from feed_processor.content_queue import ContentQueue, QueuedContent

@pytest.fixture
def queue():
    return ContentQueue(max_size=100, dedup_window=3600)

def test_simple_queue(queue):
    """Basic test to verify queue operations"""
    content = {"test": "data"}
    result = queue.enqueue("test1", content)
    assert result is not None
    assert result.content_id == "test1"

def test_enqueue_dequeue_basic(queue):
    content = {"title": "Test", "body": "Content"}
    queued = queue.enqueue("test1", content)
    assert queued is not None
    assert queued.content_id == "test1"
    assert queued.content == content
    
    dequeued = queue.dequeue()
    assert dequeued == queued
    assert queue.get_queue_size() == 0

def test_duplicate_detection(queue):
    content = {"title": "Test", "body": "Content"}
    
    # First attempt should succeed
    first = queue.enqueue("test1", content)
    assert first is not None
    
    # Second attempt with same content should fail
    second = queue.enqueue("test2", content)
    assert second is None

def test_dedup_window(queue):
    content = {"title": "Test", "body": "Content"}
    
    # Set a very short dedup window for testing
    queue.dedup_window = 0.1
    
    # First enqueue
    first = queue.enqueue("test1", content)
    assert first is not None
    
    # Wait for dedup window to expire
    time.sleep(0.2)
    
    # Should be able to enqueue same content again
    second = queue.enqueue("test2", content)
    assert second is not None

def test_retry_mechanism(queue):
    content = {"title": "Test", "body": "Content"}
    queued = queue.enqueue("test1", content)
    
    # First retry
    assert queue.mark_failed(queued, max_retries=2) is True
    assert queued.retry_count == 1
    
    # Second retry
    assert queue.mark_failed(queued, max_retries=2) is True
    assert queued.retry_count == 2
    
    # Third retry should fail (exceeds max_retries)
    assert queue.mark_failed(queued, max_retries=2) is False
    assert queued.retry_count == 3
    assert queued.processing_status == "failed"

def test_queue_stats(queue):
    content1 = {"title": "Test1", "body": "Content1"}
    content2 = {"title": "Test2", "body": "Content2"}
    
    queue.enqueue("test1", content1)
    queue.enqueue("test2", content2)
    
    stats = queue.get_queue_stats()
    assert stats["queue_size"] == 2
    assert stats["unique_contents"] == 2
    assert stats["oldest_item_age"] >= 0

def test_max_size_limit(queue):
    # Set a small max size for testing
    queue = ContentQueue(max_size=2, dedup_window=3600)
    
    # Add three items
    queue.enqueue("test1", {"id": 1})
    queue.enqueue("test2", {"id": 2})
    queue.enqueue("test3", {"id": 3})
    
    # Queue should only contain the last two items
    assert queue.get_queue_size() == 2
    
    item = queue.dequeue()
    assert item.content["id"] == 2  # First item should have been dropped
