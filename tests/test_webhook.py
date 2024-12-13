import json
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from feed_processor.webhook import WebhookConfig, WebhookError, WebhookManager, WebhookResponse


class TestWebhookManager(unittest.TestCase):
    def setUp(self):
        self.config = WebhookConfig(
            endpoint="https://example.com/webhook",
            auth_token="test-token",
            max_retries=3,
            retry_delay=1,
            timeout=5,
            batch_size=10,
        )
        self.manager = WebhookManager(self.config)
        self.sample_feed = {
            "type": "rss",
            "title": "Test Feed",
            "link": "http://example.com/feed",
            "updated": datetime.now(),
            "items": [],
        }

    def test_webhook_config_validation(self):
        # Test valid config
        config = WebhookConfig(endpoint="https://example.com/webhook", auth_token="test-token")
        self.assertIsInstance(config, WebhookConfig)

        # Test invalid endpoint
        with self.assertRaises(ValueError):
            WebhookConfig(endpoint="not-a-url", auth_token="test-token")

    def test_send_success(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"status": "success"}

            response = self.manager.send(self.sample_feed)

            self.assertTrue(response.success)
            self.assertEqual(response.status_code, 200)
            mock_post.assert_called_once()

    def test_send_failure_with_retry(self):
        with patch("requests.post") as mock_post:
            # First two calls fail, third succeeds
            mock_post.side_effect = [
                Mock(status_code=500),
                Mock(status_code=500),
                Mock(status_code=200, json=lambda: {"status": "success"}),
            ]

            response = self.manager.send(self.sample_feed)

            self.assertTrue(response.success)
            self.assertEqual(response.retry_count, 2)
            self.assertEqual(mock_post.call_count, 3)

    def test_send_failure_max_retries(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 500

            response = self.manager.send(self.sample_feed)

            self.assertFalse(response.success)
            self.assertEqual(response.retry_count, self.config.max_retries)
            self.assertEqual(mock_post.call_count, self.config.max_retries + 1)

    def test_batch_send(self):
        feeds = [self.sample_feed.copy() for _ in range(5)]

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"status": "success"}

            responses = self.manager.batch_send(feeds)

            self.assertEqual(len(responses), 1)  # One batch
            self.assertTrue(all(r.success for r in responses))
            mock_post.assert_called_once()

    def test_rate_limiting(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 429  # Too Many Requests
            mock_post.return_value.headers = {"Retry-After": "2"}

            response = self.manager.send(self.sample_feed)

            self.assertFalse(response.success)
            self.assertEqual(response.status_code, 429)
            self.assertTrue(response.rate_limited)

    def test_authentication_error(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 401

            response = self.manager.send(self.sample_feed)

            self.assertFalse(response.success)
            self.assertEqual(response.status_code, 401)
            self.assertIn("authentication", response.error_message.lower())

    def test_payload_validation(self):
        # Test invalid payload
        invalid_feed = {"type": "unknown"}
        with self.assertRaises(WebhookError):
            self.manager.send(invalid_feed)


if __name__ == "__main__":
    unittest.main()
