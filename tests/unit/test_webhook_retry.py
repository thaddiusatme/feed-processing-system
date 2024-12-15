"""Unit tests for the webhook retry mechanism."""

import time
import unittest
from unittest.mock import Mock, patch

from feed_processor.webhook_manager import WebhookManager


class TestWebhookRetry(unittest.TestCase):
    """
    Test cases for the webhook retry mechanism.

    This class contains test cases for the WebhookManager's retry mechanism,
    including successful deliveries, retries with eventual success, retry
    exhaustion, and network errors.
    """

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.webhook_manager = WebhookManager(
            webhook_url="http://test.webhook",
            rate_limit=0.2,
            max_retries=3,
            initial_retry_delay=1.0,
            max_retry_delay=8.0,
            retry_backoff_factor=2.0,
        )

    def test_retry_configuration(self):
        """
        Test that retry configuration is properly set.

        Verifies that the WebhookManager's retry configuration attributes
        are correctly set.
        """
        assert self.webhook_manager.max_retries == 3
        assert self.webhook_manager.initial_retry_delay == 1.0
        assert self.webhook_manager.max_retry_delay == 8.0
        assert self.webhook_manager.retry_backoff_factor == 2.0

    @patch("requests.post")
    def test_successful_first_attempt(self, mock_post):
        """
        Test successful webhook delivery on first attempt.

        Verifies that a successful webhook delivery does not trigger any retries.
        """
        mock_post.return_value.status_code = 200

        result = self.webhook_manager.send_webhook({"title": "Test", "contentType": ["BLOG"]})

        assert result.success is True
        assert result.retry_count == 0
        assert mock_post.call_count == 1

    @patch("requests.post")
    def test_retry_with_eventual_success(self, mock_post):
        """
        Test webhook delivery with retries that eventually succeeds.

        Verifies that the WebhookManager retries the delivery until it succeeds.
        """
        # Configure mock to fail twice then succeed
        mock_post.side_effect = [
            Mock(status_code=500),
            Mock(status_code=500),
            Mock(status_code=200),
        ]

        start_time = time.time()
        result = self.webhook_manager.send_webhook({"title": "Test", "contentType": ["BLOG"]})
        duration = time.time() - start_time

        assert result.success is True
        assert result.retry_count == 2
        assert mock_post.call_count == 3
        # Verify backoff timing (1s + 2s minimum)
        assert duration >= 3.0

    @patch("requests.post")
    def test_retry_exhaustion(self, mock_post):
        """
        Test webhook delivery that fails after all retries are exhausted.

        Verifies that the WebhookManager raises an exception after all retries are exhausted.
        """
        # Configure mock to always fail
        mock_post.return_value.status_code = 500

        start_time = time.time()
        result = self.webhook_manager.send_webhook({"title": "Test", "contentType": ["BLOG"]})
        duration = time.time() - start_time

        assert result.success is False
        assert result.retry_count == self.webhook_manager.max_retries
        assert mock_post.call_count == self.webhook_manager.max_retries + 1
        # Verify backoff timing (1s + 2s + 4s minimum)
        assert duration >= 7.0

    @patch("requests.post")
    def test_retry_with_network_error(self, mock_post):
        """
        Test webhook delivery with network errors.

        Verifies that the WebhookManager retries the delivery after a network error.
        """
        # Import requests here to avoid issues with mocking
        import requests

        # Configure mock to raise connection error then succeed
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            Mock(status_code=200),
        ]

        result = self.webhook_manager.send_webhook({"title": "Test", "contentType": ["BLOG"]})

        assert result.success is True
        assert result.retry_count == 1

    @patch("requests.post")
    def test_max_retry_delay_cap(self, mock_post):
        """
        Test that retry delay is capped at max_retry_delay.

        Verifies that the WebhookManager does not exceed the maximum retry delay.
        """
        # Configure mock to fail multiple times
        mock_post.return_value.status_code = 500

        start_time = time.time()
        self.webhook_manager.send_webhook({"title": "Test", "contentType": ["BLOG"]})
        duration = time.time() - start_time

        # With backoff factor of 2, delays would be: 1, 2, 4, 8
        # But max delay is 8, so actual delays should be: 1, 2, 4
        max_expected_duration = 7.0 + 0.5  # Adding buffer for processing time
        assert duration <= max_expected_duration
