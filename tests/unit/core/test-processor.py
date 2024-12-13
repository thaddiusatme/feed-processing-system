import json
import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

# Import will be implemented when we create the actual module
# from feed_processor.core.processor import FeedProcessor, RateLimiter, ProcessingMetrics


class TestRateLimiter:
    def test_rate_limiter_delays_requests(self):
        """Test that rate limiter enforces minimum delay between requests"""
        from feed_processor.core.processor import RateLimiter

        limiter = RateLimiter(min_interval=0.2)

        # Record start time
        start_time = time.time()

        # Make multiple requests
        for _ in range(3):
            limiter.wait()

        # Check total time
        elapsed = time.time() - start_time
        assert elapsed >= 0.4, "Rate limiter should enforce minimum delay"


class TestProcessingMetrics:
    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        from feed_processor.core.processor import ProcessingMetrics

        metrics = ProcessingMetrics()
        metrics.processed_count = 90
        metrics.error_count = 10

        assert metrics.get_error_rate() == 10.0, "Error rate should be calculated correctly"

    def test_error_rate_with_no_processing(self):
        """Test error rate when no items processed"""
        from feed_processor.core.processor import ProcessingMetrics

        metrics = ProcessingMetrics()
        assert metrics.get_error_rate() == 0, "Error rate should be 0 when no items processed"


@pytest.fixture
def mock_feed_item():
    """Fixture providing a sample feed item"""
    return {
        "title": "Test Article",
        "id": "test123",
        "published": "2024-12-12T12:00:00Z",
        "canonical": [{"href": "https://example.com/article"}],
        "author": "Test Author",
        "categories": ["test", "example"],
        "summary": {"content": "This is a test article content"},
    }


class TestFeedProcessor:
    @pytest.fixture
    def processor(self):
        """Fixture providing a configured FeedProcessor instance"""
        from feed_processor.core.processor import FeedProcessor

        return FeedProcessor(inoreader_token="test_token", webhook_url="http://test.webhook")

    def test_initialization(self, processor):
        """Test processor initialization"""
        assert processor.inoreader_token == "test_token"
        assert processor.webhook_url == "http://test.webhook"
        assert not processor.processing
        assert processor.metrics is not None

    @patch("requests.get")
    def test_fetch_feeds(self, mock_get, processor, mock_feed_item):
        """Test fetching feeds from Inoreader"""
        mock_response = Mock()
        mock_response.json.return_value = {"items": [mock_feed_item]}
        mock_get.return_value = mock_response

        processor.fetch_feeds()

        assert processor.queue.qsize() == 1, "Feed item should be added to queue"
        assert mock_get.called_with(
            "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list",
            headers={"Authorization": "Bearer test_token"},
        )

    def test_process_item(self, processor, mock_feed_item):
        """Test processing a single feed item"""
        processed = processor._process_item(mock_feed_item)

        assert processed["title"] == "Test Article"
        assert "contentType" in processed
        assert "brief" in processed
        assert "sourceMetadata" in processed
        assert "contentHash" in processed

    @patch("requests.post")
    def test_webhook_rate_limiting(self, mock_post, processor):
        """Test that webhook calls respect rate limiting"""
        mock_post.return_value.status_code = 200

        start_time = time.time()

        # Send multiple webhook requests
        for _ in range(3):
            processor._send_to_webhook({"test": "data"})

        elapsed = time.time() - start_time
        assert elapsed >= 0.4, "Webhook calls should respect rate limiting"

    def test_content_type_detection(self, processor):
        """Test content type detection logic"""
        # Test video detection
        video_item = {"canonical": [{"href": "https://youtube.com/watch?v=123"}]}
        assert "VIDEO" in processor._detect_content_type(video_item)

        # Test social detection
        social_item = {"canonical": [{"href": "https://twitter.com/user/status/123"}]}
        assert "SOCIAL" in processor._detect_content_type(social_item)

        # Test blog detection
        blog_item = {"canonical": [{"href": "https://example.com/blog"}]}
        assert "BLOG" in processor._detect_content_type(blog_item)

    def test_metrics_tracking(self, processor, mock_feed_item):
        """Test that metrics are tracked correctly during processing"""
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            # Process an item
            processor.start()
            processor.queue.put(mock_feed_item)
            time.sleep(0.5)  # Allow time for processing
            processor.stop()

            metrics = processor.get_metrics()
            assert metrics["processed_count"] == 1
            assert metrics["error_count"] == 0
            assert metrics["queue_length"] == 0

    def test_error_handling(self, processor, mock_feed_item):
        """Test error handling during processing"""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Test error")

            processor.start()
            processor.queue.put(mock_feed_item)
            time.sleep(0.5)  # Allow time for processing
            processor.stop()

            metrics = processor.get_metrics()
            assert metrics["error_count"] == 1

    @pytest.mark.integration
    def test_end_to_end_processing(self, processor, mock_feed_item):
        """Test end-to-end processing flow"""
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            mock_get.return_value.json.return_value = {"items": [mock_feed_item]}
            mock_post.return_value.status_code = 200

            processor.start()
            processor.fetch_feeds()
            time.sleep(1)  # Allow time for processing
            processor.stop()

            metrics = processor.get_metrics()
            assert metrics["processed_count"] == 1
            assert metrics["error_count"] == 0
