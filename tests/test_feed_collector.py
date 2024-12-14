"""Tests for feed collector implementation."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feed_processor.core.feed_collector import FeedCollector, FeedCollectorConfig
from feed_processor.inoreader.client import InoreaderConfig
from feed_processor.storage.models import ContentItem, ContentStatus, ContentType
from feed_processor.storage.sqlite_storage import SQLiteConfig


@pytest.fixture
def sample_items():
    """Fixture providing sample content items."""
    return [
        ContentItem(
            title=f"Test Item {i}",
            content=f"Test content {i}",
            url=f"https://example.com/test{i}",
            content_type=ContentType.BLOG,
            published_at=datetime.now(timezone.utc),
            source_id=f"test_source_{i}",
            status=ContentStatus.PENDING,
            author=f"Test Author {i}",
        )
        for i in range(3)
    ]


@pytest.fixture
def mock_storage():
    """Fixture providing a mock storage instance."""
    storage = MagicMock()
    storage.is_duplicate.return_value = False
    storage.store_item.return_value = True
    return storage


@pytest.fixture
def mock_client(sample_items):
    """Fixture providing a mock Inoreader client."""
    client = MagicMock()
    client.get_stream_contents = AsyncMock(return_value=sample_items)
    return client


@pytest.fixture
def collector(mock_storage, mock_client):
    """Fixture providing a FeedCollector instance with mocked dependencies."""
    config = FeedCollectorConfig(
        inoreader=InoreaderConfig(api_token="test_token"),
        storage=SQLiteConfig(db_path=":memory:"),
        collection_interval=0.1,
    )

    collector = FeedCollector(config)
    collector.storage = mock_storage
    collector.client = mock_client
    return collector


@pytest.mark.asyncio
async def test_collect_feeds(collector, sample_items, mock_storage):
    """Test collecting feeds from Inoreader."""
    await collector.collect_feeds()

    assert collector.client.get_stream_contents.called
    assert mock_storage.store_item.call_count == len(sample_items)


@pytest.mark.asyncio
async def test_collect_feeds_with_duplicates(collector, sample_items, mock_storage):
    """Test collecting feeds with duplicate items."""
    mock_storage.is_duplicate.return_value = True

    await collector.collect_feeds()

    assert mock_storage.store_item.call_count == 0


@pytest.mark.asyncio
async def test_collect_feeds_with_storage_error(collector, sample_items, mock_storage):
    """Test collecting feeds with storage errors."""
    mock_storage.store_item.return_value = False

    await collector.collect_feeds()

    assert mock_storage.log_error.called


@pytest.mark.asyncio
async def test_start_and_stop(collector):
    """Test starting and stopping the collector."""
    # Mock collect_feeds to avoid actual collection
    collector.collect_feeds = AsyncMock()

    # Start collector in background task
    task = asyncio.create_task(collector.start())

    # Wait for collector to start
    await asyncio.sleep(0.2)
    assert collector.running

    # Stop collector
    collector.stop()
    await task

    assert not collector.running
    assert collector.collect_feeds.called


@pytest.mark.asyncio
async def test_start_when_already_running(collector):
    """Test starting collector when it's already running."""
    collector.running = True
    collector.collect_feeds = AsyncMock()

    await collector.start()

    assert not collector.collect_feeds.called


@pytest.mark.asyncio
async def test_collection_error_handling(collector, mock_storage):
    """Test error handling during collection."""
    collector.client.get_stream_contents = AsyncMock(side_effect=Exception("Test error"))

    await collector.collect_feeds()

    assert mock_storage.log_error.called
    assert mock_storage.log_error.call_args[0] == ("collection_error", "Test error")
