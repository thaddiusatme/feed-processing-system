import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from feed_processor.feed_processor import FeedProcessor
from feed_processor.priority_queue import Priority, QueueItem
from feed_processor.webhook_manager import WebhookManager, WebhookResponse


@pytest.fixture
def mock_inoreader_response():
    return {
        "items": [
            {
                "id": "feed/1/item/1",
                "title": "Test Article 1",
                "author": "Test Author",
                "summary": {"content": "Test content"},
                "canonical": [{"href": "http://test.com/article1"}],
                "published": int(datetime(2024, 12, 13, tzinfo=timezone.utc).timestamp()),
                "categories": [{"label": "Technology"}, {"label": "Breaking News"}],
            },
            {
                "id": "feed/1/item/2",
                "title": "Test Article 2",
                "author": "Test Author 2",
                "summary": {"content": "Test content 2"},
                "canonical": [{"href": "http://test.com/article2"}],
                "published": int(datetime(2024, 12, 12, tzinfo=timezone.utc).timestamp()),
                "categories": [{"label": "Technology"}],
            },
        ],
        "continuation": "token123",
    }


@pytest.fixture
def feed_processor():
    return FeedProcessor(
        inoreader_token="test_token",
        webhook_url="http://test.webhook",
        queue_size=100,
        webhook_rate_limit=0.1,
    )


def test_feed_processor_initialization():
    """Test FeedProcessor initialization with correct parameters."""
    processor = FeedProcessor(
        inoreader_token="test_token",
        webhook_url="http://test.webhook",
        queue_size=100,
        webhook_rate_limit=0.1,
    )

    assert processor.inoreader_token == "test_token"
    assert processor.queue.max_size == 100
    assert processor.webhook_manager.rate_limit == 0.1


@patch("requests.get")
def test_fetch_feeds_success(mock_get, feed_processor, mock_inoreader_response):
    """Test successful feed fetching from Inoreader API."""
    mock_response = Mock()
    mock_response.json.return_value = mock_inoreader_response
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    response = feed_processor._fetch_feeds()

    assert response == mock_inoreader_response
    mock_get.assert_called_once_with(
        "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list",
        headers={"Authorization": "Bearer test_token", "Content-Type": "application/json"},
        params={"n": 100},
    )


@patch("requests.get")
def test_fetch_feeds_with_continuation(mock_get, feed_processor, mock_inoreader_response):
    """Test feed fetching with continuation token."""
    mock_response = Mock()
    mock_response.json.return_value = mock_inoreader_response
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    response = feed_processor._fetch_feeds("token123")

    mock_get.assert_called_once_with(
        "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list",
        headers={"Authorization": "Bearer test_token", "Content-Type": "application/json"},
        params={"n": 100, "c": "token123"},
    )


@patch("requests.get")
def test_fetch_feeds_error(mock_get, feed_processor):
    """Test error handling during feed fetching."""
    mock_get.side_effect = Exception("API Error")

    response = feed_processor._fetch_feeds()

    assert response == {}


def test_process_item_success(feed_processor, mock_inoreader_response):
    """Test successful processing of a feed item."""
    raw_item = mock_inoreader_response["items"][0]
    processed = feed_processor._process_item(raw_item)

    assert processed["id"] == "feed/1/item/1"
    assert processed["title"] == "Test Article 1"
    assert processed["author"] == "Test Author"
    assert processed["content"] == "Test content"
    assert processed["url"] == "http://test.com/article1"
    assert "processed_at" in processed
    assert len(processed["categories"]) == 2
    assert "Breaking News" in processed["categories"]


def test_process_item_error(feed_processor):
    """Test error handling during item processing."""
    invalid_item = {"invalid": "data"}
    processed = feed_processor._process_item(invalid_item)

    assert processed == {}


def test_determine_priority_high(feed_processor):
    """Test priority determination for breaking news."""
    item = {
        "categories": ["Technology", "Breaking News"],
        "published": datetime.now(timezone.utc).isoformat(),
    }

    priority = feed_processor._determine_priority(item)
    assert priority == Priority.HIGH


def test_determine_priority_normal(feed_processor):
    """Test priority determination for recent news."""
    item = {"categories": ["Technology"], "published": datetime.now(timezone.utc).isoformat()}

    priority = feed_processor._determine_priority(item)
    assert priority == Priority.NORMAL


def test_determine_priority_low(feed_processor):
    """Test priority determination for older news."""
    old_date = datetime(2024, 12, 12, tzinfo=timezone.utc).isoformat()
    item = {"categories": ["Technology"], "published": old_date}

    priority = feed_processor._determine_priority(item)
    assert priority == Priority.LOW


@patch("requests.get")
def test_fetch_and_queue_items(mock_get, feed_processor, mock_inoreader_response):
    """Test fetching and queuing items with proper priorities."""
    # First response with continuation token
    first_response = Mock()
    first_response.json.return_value = mock_inoreader_response
    first_response.status_code = 200

    # Second response without continuation token (end of feed)
    second_response = Mock()
    second_response.json.return_value = {"items": [], "continuation": None}
    second_response.status_code = 200

    # Return different responses for each call
    mock_get.side_effect = [first_response, second_response]

    items_queued = feed_processor.fetch_and_queue_items()

    assert items_queued == 2
    assert feed_processor.queue.size == 2
    assert mock_get.call_count == 2  # Should make two API calls

    # First item should be high priority (Breaking News)
    item1 = feed_processor.queue.dequeue()
    assert item1.priority == Priority.HIGH
    assert item1.content["title"] == "Test Article 1"

    # Second item should be normal/low priority
    item2 = feed_processor.queue.dequeue()
    assert item2.content["title"] == "Test Article 2"


@patch.object(WebhookManager, "send_webhook")
def test_process_queue_success(mock_send_webhook, feed_processor):
    """Test successful processing of queued items."""
    # Add test items to queue
    feed_processor.queue.enqueue(
        QueueItem(
            id="1",
            priority=Priority.HIGH,
            content={"title": "Test 1"},
            timestamp=datetime.now(timezone.utc),
        )
    )
    feed_processor.queue.enqueue(
        QueueItem(
            id="2",
            priority=Priority.NORMAL,
            content={"title": "Test 2"},
            timestamp=datetime.now(timezone.utc),
        )
    )

    mock_send_webhook.return_value = WebhookResponse(
        success=True, status_code=200, timestamp=datetime.now(timezone.utc).isoformat()
    )

    processed = feed_processor.process_queue(batch_size=2)

    assert processed == 2
    assert feed_processor.queue.size == 0
    assert mock_send_webhook.call_count == 2


@patch.object(WebhookManager, "send_webhook")
def test_process_queue_with_errors(mock_send_webhook, feed_processor):
    """Test queue processing with webhook errors."""
    feed_processor.queue.enqueue(
        QueueItem(
            id="1",
            priority=Priority.HIGH,
            content={"title": "Test 1"},
            timestamp=datetime.now(timezone.utc),
        )
    )

    mock_send_webhook.return_value = WebhookResponse(
        success=False,
        status_code=500,
        error_id="error123",
        error_type="ServerError",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    processed = feed_processor.process_queue(batch_size=1)

    assert processed == 0  # No items successfully processed
    assert mock_send_webhook.call_count == 1
