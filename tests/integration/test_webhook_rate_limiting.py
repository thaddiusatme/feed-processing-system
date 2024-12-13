import pytest
import time
from datetime import datetime, timezone, timedelta
import threading
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from feed_processor.webhook_manager import WebhookManager, WebhookResponse
from feed_processor.content_queue import ContentQueue
from feed_processor.processor import FeedProcessor


class TestWebhookRateLimiting:
    @pytest.fixture
    def webhook_manager(self):
        return WebhookManager(webhook_url="http://test.webhook", rate_limit=0.2)

    @pytest.fixture
    def content_queue(self):
        return ContentQueue(max_size=1000)

    @pytest.fixture
    def processor(self, webhook_manager, content_queue):
        return FeedProcessor(
            inoreader_token="test_token",
            webhook_url="http://test.webhook",
            webhook_manager=webhook_manager,
            content_queue=content_queue,
            test_mode=True,
        )

    def is_valid_timestamp(self, timestamp_str: str, reference_time: datetime) -> bool:
        """Check if a timestamp string is within 5 seconds of a reference time."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            diff = abs((timestamp - reference_time).total_seconds())
            return diff <= 5
        except ValueError:
            return False

    @patch("requests.post")
    def test_rate_limit_compliance(self, mock_post, webhook_manager):
        """Test that webhook requests comply with rate limit."""
        mock_post.return_value.status_code = 200
        num_requests = 5
        reference_time = datetime.now(timezone.utc)
        start_time = time.time()

        # Send multiple requests
        responses = []
        for i in range(num_requests):
            response = webhook_manager.send_webhook(
                {"title": f"Test {i}", "contentType": ["BLOG"], "brief": f"Test content {i}"}
            )
            responses.append(response)

        end_time = time.time()
        duration = end_time - start_time

        # Verify timing
        min_expected_duration = (num_requests - 1) * 0.2
        max_expected_duration = min_expected_duration + 0.1
        assert (
            min_expected_duration <= duration <= max_expected_duration
        ), f"Duration {duration:.2f}s outside expected range [{min_expected_duration:.2f}, {max_expected_duration:.2f}]"

        # Verify all requests were successful
        assert all(r.success for r in responses)
        # Verify timestamps are within acceptable range
        assert all(self.is_valid_timestamp(r.timestamp, reference_time) for r in responses)
        # Verify the number of calls
        assert mock_post.call_count == num_requests

    @patch("requests.post")
    def test_concurrent_webhook_delivery(self, mock_post, webhook_manager):
        """Test rate limiting under concurrent load."""
        mock_post.return_value.status_code = 200
        num_threads = 3
        requests_per_thread = 2
        reference_time = datetime.now(timezone.utc)

        def worker():
            responses = []
            for i in range(requests_per_thread):
                response = webhook_manager.send_webhook(
                    {
                        "title": f"Test {threading.get_ident()}-{i}",
                        "contentType": ["BLOG"],
                        "brief": f"Test content {i}",
                    }
                )
                responses.append(response)
            return responses

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            all_responses = []
            for future in as_completed(futures):
                all_responses.extend(future.result())

        end_time = time.time()
        duration = end_time - start_time

        total_requests = num_threads * requests_per_thread

        # Verify timing
        min_expected_duration = (total_requests - 1) * 0.2
        max_expected_duration = min_expected_duration + 0.2
        assert (
            min_expected_duration <= duration <= max_expected_duration
        ), f"Duration {duration:.2f}s outside expected range [{min_expected_duration:.2f}, {max_expected_duration:.2f}]"

        # Verify all requests were successful
        assert all(r.success for r in all_responses)
        # Verify timestamps are within acceptable range
        assert all(self.is_valid_timestamp(r.timestamp, reference_time) for r in all_responses)
        # Verify the number of calls
        assert mock_post.call_count == total_requests
        # Verify we got the expected number of responses
        assert len(all_responses) == total_requests

    @patch("requests.post")
    def test_end_to_end_processing(self, mock_post, processor):
        """Test end-to-end processing with rate limiting."""
        mock_post.return_value.status_code = 200
        num_items = 3
        reference_time = datetime.now(timezone.utc)

        # Add items to queue
        for i in range(num_items):
            processor.queue.enqueue(
                {
                    "id": f"test_{i}",
                    "title": f"Test {i}",
                    "contentType": ["BLOG"],
                    "brief": f"Test content {i}",
                }
            )

        start_time = time.time()

        # Process items
        processed_items = []
        while len(processed_items) < num_items and (time.time() - start_time) < 5:
            item = processor.queue.dequeue()
            if item:
                response = processor.send_to_webhook(item.content)
                if response.success:
                    processed_items.append(item)
                    processor.queue.mark_processed(item)

        end_time = time.time()
        duration = end_time - start_time

        # Verify timing
        min_expected_duration = (num_items - 1) * 0.2
        max_expected_duration = min_expected_duration + 0.1
        assert (
            min_expected_duration <= duration <= max_expected_duration
        ), f"Duration {duration:.2f}s outside expected range [{min_expected_duration:.2f}, {max_expected_duration:.2f}]"

        # Verify queue is empty
        assert processor.queue.size == 0
        # Verify all items were processed
        assert len(processed_items) == num_items
        # Verify the number of webhook calls
        assert mock_post.call_count == num_items
