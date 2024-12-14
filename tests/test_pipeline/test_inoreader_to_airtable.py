"""Tests for the Inoreader to Airtable pipeline."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feed_processor.core.clients import InoreaderClient
from feed_processor.pipeline.inoreader_to_airtable import InoreaderToAirtablePipeline
from feed_processor.queues.content import ContentQueue, QueuedContent
from feed_processor.storage import AirtableClient, ContentItem, ContentStatus, ContentType


@pytest.fixture
def mock_inoreader_client():
    client = AsyncMock(spec=InoreaderClient)
    return client


@pytest.fixture
def mock_airtable_client():
    client = AsyncMock(spec=AirtableClient)
    return client


@pytest.fixture
def mock_content_queue():
    queue = MagicMock(spec=ContentQueue)
    queue.size = 0
    queue.is_empty.return_value = True
    return queue


@pytest.fixture
def sample_content_items():
    return [
        ContentItem(
            title="Test Article 1",
            content="Test content 1",
            url="https://example.com/1",
            content_type=ContentType.BLOG,
            published_at=datetime.now(timezone.utc),
            source_id="test1",
            status=ContentStatus.PENDING,
        ),
        ContentItem(
            title="Test Article 2",
            content="Test content 2",
            url="https://example.com/2",
            content_type=ContentType.VIDEO,
            published_at=datetime.now(timezone.utc),
            source_id="test2",
            status=ContentStatus.PENDING,
        ),
    ]


@pytest.fixture
def pipeline(mock_inoreader_client, mock_airtable_client, mock_content_queue):
    return InoreaderToAirtablePipeline(
        inoreader_client=mock_inoreader_client,
        airtable_client=mock_airtable_client,
        content_queue=mock_content_queue,
        batch_size=2,
    )


@pytest.mark.asyncio
async def test_fetch_and_queue_items_success(
    pipeline, mock_inoreader_client, mock_content_queue, sample_content_items
):
    """Test successful fetching and queuing of items."""
    # Setup
    mock_inoreader_client.get_stream_contents.return_value = sample_content_items
    mock_content_queue.enqueue.return_value = True

    # Execute
    items_queued = await pipeline.fetch_and_queue_items()

    # Assert
    assert items_queued == len(sample_content_items)
    assert mock_inoreader_client.get_stream_contents.called
    assert mock_content_queue.enqueue.call_count == len(sample_content_items)


@pytest.mark.asyncio
async def test_fetch_and_queue_items_empty(pipeline, mock_inoreader_client):
    """Test handling of empty response from Inoreader."""
    # Setup
    mock_inoreader_client.get_stream_contents.return_value = []

    # Execute
    items_queued = await pipeline.fetch_and_queue_items()

    # Assert
    assert items_queued == 0
    assert mock_inoreader_client.get_stream_contents.called


@pytest.mark.asyncio
async def test_fetch_and_queue_items_error(pipeline, mock_inoreader_client):
    """Test error handling during fetch operation."""
    # Setup
    mock_inoreader_client.get_stream_contents.side_effect = Exception("API Error")

    # Execute
    items_queued = await pipeline.fetch_and_queue_items()

    # Assert
    assert items_queued == 0
    assert mock_inoreader_client.get_stream_contents.called


@pytest.mark.asyncio
async def test_process_and_store_batch_success(
    pipeline, mock_content_queue, mock_airtable_client, sample_content_items
):
    """Test successful processing and storing of a batch."""
    # Setup
    mock_content_queue.is_empty.side_effect = [False, False, True]
    mock_content_queue.dequeue.side_effect = [
        QueuedContent(
            content_id=item.source_id, content=item.dict(), timestamp=datetime.now(timezone.utc)
        )
        for item in sample_content_items
    ]

    # Execute
    processed_count = await pipeline.process_and_store_batch()

    # Assert
    assert processed_count == len(sample_content_items)
    assert mock_airtable_client.create_records.called
    assert mock_content_queue.dequeue.call_count == len(sample_content_items)


@pytest.mark.asyncio
async def test_process_and_store_batch_empty_queue(pipeline, mock_content_queue):
    """Test processing with empty queue."""
    # Setup
    mock_content_queue.is_empty.return_value = True

    # Execute
    processed_count = await pipeline.process_and_store_batch()

    # Assert
    assert processed_count == 0
    assert not mock_content_queue.dequeue.called


@pytest.mark.asyncio
async def test_process_and_store_batch_error(
    pipeline, mock_content_queue, mock_airtable_client, sample_content_items
):
    """Test error handling during batch processing."""
    # Setup
    mock_content_queue.is_empty.side_effect = [False, False, True]
    mock_content_queue.dequeue.side_effect = [
        QueuedContent(
            content_id=item.source_id, content=item.dict(), timestamp=datetime.now(timezone.utc)
        )
        for item in sample_content_items
    ]
    mock_airtable_client.create_records.side_effect = Exception("Storage Error")

    # Execute
    processed_count = await pipeline.process_and_store_batch()

    # Assert
    assert processed_count == len(sample_content_items)
    assert mock_airtable_client.create_records.called
    # Verify items are requeued on error
    assert mock_content_queue.enqueue.call_count == len(sample_content_items)


@pytest.mark.asyncio
async def test_run_pipeline_graceful_shutdown(pipeline):
    """Test graceful shutdown of pipeline."""

    # Setup
    async def stop_after_delay():
        await asyncio.sleep(0.1)
        pipeline.stop()

    # Execute
    asyncio.create_task(stop_after_delay())
    await pipeline.run(interval=0.05)

    # Assert pipeline stopped
    assert not pipeline.running


@pytest.mark.asyncio
async def test_metrics_initialization(pipeline):
    """Test metrics are properly initialized."""
    # Verify metrics were registered
    from prometheus_client.registry import REGISTRY

    metrics = [metric.name for metric in REGISTRY.collect()]
    expected_metrics = [
        "pipeline_items_processed_total",
        "pipeline_processing_duration_seconds",
        "pipeline_queue_size",
    ]

    for metric in expected_metrics:
        assert metric in metrics
