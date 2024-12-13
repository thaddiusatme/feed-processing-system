import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from feed_processor.content_queue import ContentQueue, QueueItem
from feed_processor.processor import FeedProcessor
from feed_processor.webhook_manager import WebhookManager, WebhookResponse


@pytest.fixture
def webhook_manager():
    return WebhookManager(
        webhook_url="https://test-webhook.example.com/endpoint",
        rate_limit=0.1,  # Shorter for testing
        max_retries=2,
    )


@pytest.fixture
def content_queue():
    return ContentQueue(max_size=100, deduplication_window=60)


@pytest.fixture
def feed_processor(webhook_manager, content_queue):
    return FeedProcessor(
        webhook_manager=webhook_manager,
        content_queue=content_queue,
        batch_size=5,
        processing_interval=0.1,
    )


@pytest.fixture
def sample_content_item():
    return {
        "id": "test123",
        "title": "Test Article",
        "summary": {"content": "This is a test article for integration testing"},
        "canonical": [{"href": "https://example.com/test-article"}],
        "published": "2024-12-12T12:00:00Z",
        "author": "Test Author",
        "categories": ["test", "integration"],
    }


def test_content_transformation(feed_processor, sample_content_item):
    webhook_payload = feed_processor._transform_to_webhook_payload(sample_content_item)

    assert webhook_payload["title"] == sample_content_item["title"]
    assert webhook_payload["contentType"] == ["BLOG"]
    assert webhook_payload["brief"] == sample_content_item["summary"]["content"]
    assert webhook_payload["sourceMetadata"]["feedId"] == sample_content_item["id"]
    assert (
        webhook_payload["sourceMetadata"]["originalUrl"]
        == sample_content_item["canonical"][0]["href"]
    )


def test_content_type_detection(feed_processor):
    video_item = {
        "canonical": [{"href": "https://youtube.com/watch?v=123"}],
        "title": "",
        "summary": {"content": ""},
    }
    social_item = {
        "canonical": [{"href": "https://twitter.com/user/status/123"}],
        "title": "",
        "summary": {"content": ""},
    }
    blog_item = {
        "canonical": [{"href": "https://example.com/blog"}],
        "title": "",
        "summary": {"content": ""},
    }

    assert feed_processor._detect_content_type(video_item) == "VIDEO"
    assert feed_processor._detect_content_type(social_item) == "SOCIAL"
    assert feed_processor._detect_content_type(blog_item) == "BLOG"


def test_priority_calculation(feed_processor):
    high_priority = {
        "title": "BREAKING: Important News",
        "summary": {"content": "Urgent update on..."},
    }
    medium_priority = {"title": "New Feature Release", "summary": {"content": "Latest updates..."}}
    low_priority = {"title": "Regular Article", "summary": {"content": "Standard content..."}}

    assert feed_processor._calculate_priority(high_priority) == "High"
    assert feed_processor._calculate_priority(medium_priority) == "Medium"
    assert feed_processor._calculate_priority(low_priority) == "Low"


@patch("requests.post")
def test_batch_processing(mock_post, feed_processor, sample_content_item):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Add items to queue
    for i in range(10):
        item = sample_content_item.copy()
        item["id"] = f"test{i}"
        feed_processor.content_queue.add(QueueItem(item["id"], item))

    # Process one batch
    feed_processor._process_batch()

    # Should have processed batch_size items
    assert mock_post.call_count == 1  # One bulk request
    assert feed_processor.content_queue.size() == 5  # Remaining items


@patch("requests.post")
def test_failed_delivery_requeue(mock_post, feed_processor, sample_content_item):
    mock_response = Mock()
    mock_response.status_code = 503  # Server error
    mock_post.return_value = mock_response

    feed_processor.content_queue.add(QueueItem(sample_content_item["id"], sample_content_item))
    initial_size = feed_processor.content_queue.size()

    feed_processor._process_batch()

    # Item should be requeued
    assert feed_processor.content_queue.size() == initial_size


def test_processor_lifecycle(feed_processor):
    # Start processor
    feed_processor.start()
    assert feed_processor.processing is True
    assert feed_processor.process_thread.is_alive()

    # Stop processor
    feed_processor.stop()
    assert feed_processor.processing is False
    assert not feed_processor.process_thread.is_alive()


@patch("requests.post")
def test_end_to_end_processing(mock_post, feed_processor, sample_content_item):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Add items to queue
    for i in range(3):
        item = sample_content_item.copy()
        item["id"] = f"test{i}"
        feed_processor.content_queue.add(QueueItem(item["id"], item))

    # Start processing
    feed_processor.start()

    # Wait for processing
    time.sleep(0.5)

    # Stop processing
    feed_processor.stop()

    # Verify all items were processed
    assert feed_processor.content_queue.empty()
    assert mock_post.call_count >= 1  # At least one webhook call made
