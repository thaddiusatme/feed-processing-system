"""Unit tests for the feed processor module."""

from datetime import datetime, timezone

import pytest

from feed_processor.content_queue import ContentQueue
from feed_processor.database import Database
from feed_processor.error_handler import ErrorHandler
from feed_processor.processor import FeedProcessor
from feed_processor.storage.airtable_client import AirtableConfig
from feed_processor.webhook_manager import WebhookResponse


def create_mock_inoreader_response():
    """Create a mock Inoreader response for testing purposes.

    Returns:
        A dictionary representing a mock Inoreader response.
    """
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
def mock_inoreader_response():
    """Mock Inoreader response fixture."""
    return create_mock_inoreader_response()


@pytest.fixture
def feed_processor():
    """Feed processor fixture."""
    content_queue = ContentQueue(max_size=100)
    db = Database()
    error_handler = ErrorHandler()
    airtable_config = AirtableConfig(
        api_key="test-key", base_id="test-base", table_name="test-table"
    )

    return FeedProcessor(
        content_queue=content_queue,
        db=db,
        airtable_config=airtable_config,
        error_handler=error_handler,
        batch_size=10,
        processing_interval=60,
    )


@pytest.mark.asyncio
async def test_feed_processor_initialization(feed_processor):
    """Test FeedProcessor initialization with correct parameters."""
    assert isinstance(feed_processor.content_queue, ContentQueue)
    assert isinstance(feed_processor.db, Database)
    assert isinstance(feed_processor.error_handler, ErrorHandler)
    assert feed_processor.batch_size == 10
    assert feed_processor.processing_interval == 60


@pytest.mark.asyncio
async def test_process_item_success(feed_processor, mock_inoreader_response):
    """Test successful processing of a feed item."""
    item = mock_inoreader_response["items"][0]
    processed = await feed_processor.process_item(item)
    assert processed["id"] == "feed/1/item/1"
    assert processed["title"] == "Test Article 1"
    assert processed["author"] == "Test Author"


@pytest.mark.asyncio
async def test_process_item_error(feed_processor):
    """Test error handling during item processing."""
    invalid_item = {"id": "test", "invalid": "data"}
    processed = await feed_processor.process_item(invalid_item)
    assert processed == {}


@pytest.fixture
def mock_send_webhook(mocker):
    """Mock the webhook sending functionality."""
    return mocker.patch("feed_processor.webhook_manager.WebhookManager.send_batch")


@pytest.mark.asyncio
async def test_process_queue_success(mock_send_webhook, feed_processor):
    """Test successful processing of queued items."""
    mock_send_webhook.return_value = WebhookResponse(success=True, status_code=200)

    # Add test items to queue
    items = [{"id": "1", "title": "Test 1"}, {"id": "2", "title": "Test 2"}]
    for item in items:
        await feed_processor.content_queue.put(item)

    # Process queue
    await feed_processor.process_queue()

    assert mock_send_webhook.call_count == 1
    assert len(feed_processor.content_queue) == 0


@pytest.mark.asyncio
async def test_process_queue_with_errors(mock_send_webhook, feed_processor):
    """Test queue processing with webhook errors."""
    mock_send_webhook.side_effect = Exception("Webhook error")

    # Add test items to queue
    items = [{"id": "1", "title": "Test 1"}, {"id": "2", "title": "Test 2"}]
    for item in items:
        await feed_processor.content_queue.put(item)

    # Process queue
    await feed_processor.process_queue()

    assert mock_send_webhook.call_count > 0
    assert len(feed_processor.content_queue) > 0  # Items should remain in queue after error
