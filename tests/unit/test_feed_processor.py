"""Unit tests for the feed processor."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from feed_processor.config.processor_config import ProcessorConfig
from feed_processor.core.errors import APIError, ProcessingError
from feed_processor.core.processor import FeedProcessor, ProcessingMetrics, RateLimiter


@pytest.fixture
def config():
    """Create a test processor configuration."""
    return ProcessorConfig(
        batch_size=5,
        max_retries=2,
        processing_timeout=10,
        concurrent_processors=1,
        poll_interval=1,
        test_mode=True,
    )


@pytest.fixture
def mock_inoreader():
    """Create a mock Inoreader client."""
    mock = Mock()
    mock.get_unread_items.return_value = {
        "items": [
            {
                "id": "test-1",
                "title": "Test Item 1",
                "published": int(datetime.now().timestamp()),
                "likes": 1500,
                "shares": 600,
            }
        ]
    }
    return mock


@pytest.fixture
def mock_webhook():
    """Create a mock webhook manager."""
    mock = Mock()
    mock.deliver_batch.return_value = Mock(success=True, error=None)
    return mock


@pytest.fixture
def processor(config, mock_inoreader, mock_webhook):
    """Create a test instance of FeedProcessor."""
    with patch("feed_processor.core.processor.InoreaderClient", return_value=mock_inoreader):
        processor = FeedProcessor(
            inoreader_token="test-token",
            webhook_url="https://test.webhook.com",
            config=config,
            webhook_manager=mock_webhook,
        )
        return processor


def test_processor_initialization(processor, config):
    """Test processor initialization with configuration."""
    assert processor.config == config
    assert processor.running is False
    assert processor.processing is False
    assert isinstance(processor.metrics, ProcessingMetrics)
    assert isinstance(processor.rate_limiter, RateLimiter)


def test_detect_content_type(processor):
    """Test content type detection."""
    # Test video content
    assert processor.detect_content_type({"video_url": "test.mp4"}) == "VIDEO"
    assert processor.detect_content_type({"youtube_id": "123"}) == "VIDEO"

    # Test social content
    assert processor.detect_content_type({"social_signals": True}) == "SOCIAL"
    assert processor.detect_content_type({"likes": 100}) == "SOCIAL"

    # Test news content
    assert processor.detect_content_type({"news_score": 0.8}) == "NEWS"
    assert processor.detect_content_type({"article_text": "news"}) == "NEWS"

    # Test general content
    assert processor.detect_content_type({}) == "GENERAL"


def test_calculate_priority(processor):
    """Test priority calculation."""
    # Test engagement signals
    high_engagement = {
        "likes": 6000,
        "shares": 2500,
        "comments": 150,
        "published": int(datetime.now().timestamp()),
    }
    assert processor.calculate_priority(high_engagement) == 10

    # Test content type weights
    video_content = {"video_url": "test.mp4", "published": int(datetime.now().timestamp())}
    assert processor.calculate_priority(video_content) >= 7

    # Test freshness
    old_content = {"published": int((datetime.now() - timedelta(days=1)).timestamp())}
    assert processor.calculate_priority(old_content) == 5


def test_process_item(processor):
    """Test processing of individual items."""
    item = {"id": "test-1", "title": "Test Item", "published": int(datetime.now().timestamp())}

    processed = processor.process_item(item)
    assert "processed_at" in processed
    assert "content_type" in processed
    assert "priority" in processed
    assert "processor_version" in processed


def test_process_batch(processor):
    """Test batch processing of items."""
    items = [{"id": f"test-{i}", "title": f"Test {i}"} for i in range(3)]

    processed = processor.process_batch(items)
    assert len(processed) == 3
    assert all("processed_at" in item for item in processed)


def test_fetch_feeds(processor, mock_inoreader):
    """Test feed fetching."""
    items = processor.fetch_feeds()
    assert len(items) == 1
    assert items[0]["id"] == "test-1"
    assert processor.metrics.processed_count > 0


def test_fetch_feeds_error(processor, mock_inoreader):
    """Test feed fetching error handling."""
    mock_inoreader.get_unread_items.side_effect = APIError("API Error")
    items = processor.fetch_feeds()
    assert len(items) == 0
    assert processor.metrics.error_count > 0


def test_send_batch_to_webhook(processor, mock_webhook):
    """Test webhook batch delivery."""
    items = [{"id": "test-1", "title": "Test"}]
    assert processor.send_batch_to_webhook(items) is True
    mock_webhook.deliver_batch.assert_called_once_with(items)


def test_send_batch_to_webhook_error(processor, mock_webhook):
    """Test webhook delivery error handling."""
    mock_webhook.deliver_batch.return_value = Mock(success=False, error="Error")
    items = [{"id": "test-1", "title": "Test"}]
    assert processor.send_batch_to_webhook(items) is False
    assert processor.metrics.error_count > 0


def test_metrics_collection(processor):
    """Test metrics collection."""
    # Process some items
    items = [{"id": "test-1", "title": "Test"}]
    processor.process_batch(items)

    metrics = processor.get_metrics()
    assert metrics["processed_count"] >= 1
    assert "error_rate" in metrics
    assert "queue_length" in metrics
    assert "uptime_seconds" in metrics
    assert "prometheus_metrics" in metrics


def test_rate_limiter():
    """Test rate limiter functionality."""
    limiter = RateLimiter(min_interval=0.01, max_retries=2)

    # Test basic waiting
    start = datetime.now()
    limiter.wait()
    limiter.wait()
    duration = (datetime.now() - start).total_seconds()
    assert duration >= 0.01

    # Test exponential backoff
    with pytest.raises(ProcessingError):
        for i in range(3):  # Should exceed max_retries
            limiter.exponential_backoff(i)


def test_processing_metrics():
    """Test processing metrics calculations."""
    metrics = ProcessingMetrics()

    # Test error rate
    metrics.processed_count = 10
    metrics.error_count = 2
    assert metrics.get_error_rate() == 0.2

    # Test item tracking
    assert not metrics.has_processed("test-1")
    metrics.mark_processed("test-1")
    assert metrics.has_processed("test-1")


@patch("threading.Thread")
def test_processor_lifecycle(mock_thread, processor):
    """Test processor start/stop lifecycle."""
    # Test start
    processor.start()
    assert processor.running is True
    mock_thread.assert_not_called()  # Because test_mode is True

    # Test stop
    processor.stop()
    assert processor.running is False
    assert processor.processing is False


def test_process_loop_error_handling(processor):
    """Test process loop error handling."""
    processor.inoreader_client.get_unread_items.side_effect = Exception("Test error")

    # Run one iteration of the process loop
    processor.running = True
    processor._process_loop()

    assert processor.metrics.error_count > 0
    assert not processor.running  # Should stop on max retries
