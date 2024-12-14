import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from feed_processor.queues.content import ContentQueue
from feed_processor.core.processor import FeedProcessor
from feed_processor.webhook.manager import WebhookResponse


@pytest.fixture
def processor():
    """Create a FeedProcessor instance in test mode."""
    return FeedProcessor(
        inoreader_token="test_token", webhook_url="http://test.com/webhook", test_mode=True
    )


@pytest.fixture
def mock_queue():
    return Mock(spec=ContentQueue)


@pytest.fixture
def mock_webhook_manager():
    manager = Mock()
    manager.send_webhook.return_value = WebhookResponse(True, None, None, 200)
    return manager


def test_initialization():
    processor = FeedProcessor("test_token", "http://test.com", test_mode=True)
    assert processor.inoreader_token == "test_token"
    assert processor.webhook_url == "http://test.com"
    assert not processor.running
    assert not processor.processing
    assert processor.test_mode


@patch("requests.get")
def test_fetch_feeds_success(mock_get):
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": "1",
                "title": "Test Article 1",
                "content": {"content": "Test content 1"},
                "published": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    mock_get.return_value = mock_response

    processor = FeedProcessor("test_token", "http://test.com", test_mode=True)
    feeds = processor.fetch_feeds()

    assert len(feeds) == 1
    assert feeds[0]["id"] == "1"
    mock_get.assert_called_once()


@patch("requests.get")
def test_fetch_feeds_auth_error(mock_get):
    # Mock 403 error response
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=Mock(status_code=403)
    )
    mock_get.return_value = mock_response

    processor = FeedProcessor("invalid_token", "http://test.com", test_mode=True)
    feeds = processor.fetch_feeds()

    assert len(feeds) == 0
    assert processor.metrics.error_count == 1


def test_start_stop():
    processor = FeedProcessor("test_token", "http://test.com", test_mode=True)

    processor.start()
    assert processor.running
    assert processor.processing

    processor.stop()
    assert not processor.running
    assert not processor.processing


def test_process_item(processor):
    item = {
        "id": "1",
        "title": "Test Title",
        "content": {"content": "Test Content"},
        "published": datetime.now(timezone.utc).isoformat(),
    }

    processed = processor.process_item(item)
    assert processed["id"] == "1"
    assert processed["title"] == "Test Title"
    assert "content_type" in processed
    assert "priority" in processed


def test_process_batch(processor):
    items = [
        {
            "id": "1",
            "title": "Test 1",
            "content": {"content": "Content 1"},
            "published": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": "2",
            "title": "Test 2",
            "content": {"content": "Content 2"},
            "published": datetime.now(timezone.utc).isoformat(),
        },
    ]

    processed = processor.process_batch(items)
    assert len(processed) == 2
    assert all(isinstance(item, dict) for item in processed)
    assert processor.metrics.processed_count == 2
