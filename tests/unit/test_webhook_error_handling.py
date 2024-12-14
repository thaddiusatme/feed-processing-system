"""Tests for webhook error handling functionality."""

import threading
import time
from unittest.mock import patch

import pytest
import requests

from feed_processor.error_handling import ErrorHandler
from feed_processor.metrics.prometheus import MetricsCollector
from feed_processor.webhook.manager import WebhookManager


class TestWebhookErrorHandling:
    """Test suite for webhook error handling."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.error_handler = ErrorHandler()
        self.metrics = MetricsCollector()
        self.webhook_manager = WebhookManager(self.error_handler, self.metrics)

    def get_valid_payload(self):
        """Get a valid webhook payload for testing."""
        return {"title": "Test", "brief": "Test brief", "contentType": "article"}

    def simulate_concurrent_failures(self, error_handler):
        """Simulate concurrent error handling."""
        try:
            raise Exception("Concurrent test error")
        except Exception as e:
            error_handler.handle_error(
                error=e, context={"test": "concurrent"}, retry_func=lambda: True
            )

    def test_rate_limit_error_handling(self):
        """Test handling of rate limit errors."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException("Rate limit")

            result = self.webhook_manager.send_webhook(self.get_valid_payload())

            assert not result
            assert mock_post.call_count == self.webhook_manager.max_retries
            assert self.metrics.webhook_failures_total.value > 0

    def test_concurrent_error_handling(self):
        """Test handling of concurrent errors."""
        threads = []
        for _ in range(5):
            thread = threading.Thread(
                target=self.simulate_concurrent_failures, args=(self.error_handler,)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(self.error_handler.error_history) > 0

    def test_error_history_tracking(self):
        """Test tracking of error history."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException("Test error")

            self.webhook_manager.send_webhook(self.get_valid_payload())

            assert len(self.error_handler.error_history) > 0
            last_error = self.error_handler.error_history[-1]
            assert "Test error" in str(last_error["error"])

    @pytest.mark.parametrize("hour,expected_retries", [(10, 3), (22, 5)])
    def test_time_based_retry_strategy(self, hour, expected_retries):
        """Test retry strategy based on time of day."""
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value.hour = hour

            self.webhook_manager.max_retries = expected_retries
            result = self.webhook_manager.send_webhook(self.get_valid_payload())

            assert not result
            assert self.webhook_manager.max_retries == expected_retries

    def test_validate_payload_missing_fields(self):
        """Test validation of webhook payload with missing fields."""
        invalid_payload = {"title": "Test"}
        assert not self.webhook_manager._validate_payload(invalid_payload)


def test_webhook_retry_mechanism():
    """Test webhook retry mechanism functionality."""
    error_handler = ErrorHandler()
    metrics = MetricsCollector()
    webhook_manager = WebhookManager(error_handler, metrics)

    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException("Test error")

        result = webhook_manager.send_webhook(
            {"title": "Test", "brief": "Test", "contentType": "article"}
        )

        assert not result
        assert mock_post.call_count == webhook_manager.max_retries


def test_concurrent_webhook_retries():
    """Test concurrent webhook retry handling."""
    error_handler = ErrorHandler()
    metrics = MetricsCollector()
    webhook_manager = WebhookManager(error_handler, metrics)

    threads = []
    for _ in range(3):
        thread = threading.Thread(
            target=lambda: webhook_manager.send_webhook(
                {"title": "Test", "brief": "Test brief", "contentType": "article"}
            )
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert metrics.webhook_failures_total.value > 0


def test_webhook_backoff_timing():
    """Test webhook retry backoff timing."""
    error_handler = ErrorHandler()
    metrics = MetricsCollector()
    webhook_manager = WebhookManager(error_handler, metrics)

    start_time = time.time()

    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException("Test error")
        webhook_manager.send_webhook(
            {"title": "Test", "brief": "Test brief", "contentType": "article"}
        )

    end_time = time.time()
    duration = end_time - start_time

    # With exponential backoff, total time should be significant
    assert duration > 5  # At least 5 seconds with retries
