import unittest
from unittest.mock import Mock, patch
import json
from datetime import datetime

from feed_processor.processor import FeedProcessor
from feed_processor.webhook import WebhookManager, WebhookConfig, WebhookResponse

class TestFeedProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = FeedProcessor(
            max_queue_size=10,
            webhook_endpoint="https://example.com/webhook",
            webhook_auth_token="test-token",
            webhook_batch_size=2
        )
        self.sample_feed = {
            'content': '''
            <?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Item Description</description>
                </item>
            </channel>
            </rss>
            '''
        }

    def test_add_feed_invalid_content(self):
        """Test adding feed with invalid content."""
        self.assertFalse(self.processor.add_feed({'content': 'invalid content'}))

    def test_add_feed_queue_full(self):
        """Test adding feed when queue is full."""
        # Fill up the queue
        for _ in range(10):  # max_queue_size is 10
            self.processor.add_feed(self.sample_feed)
        
        # Try to add one more
        self.assertFalse(self.processor.add_feed(self.sample_feed))

    def test_add_feed_success(self):
        """Test successfully adding a feed."""
        self.assertTrue(self.processor.add_feed(self.sample_feed))

    def test_add_feed_with_webhook(self):
        """Test adding a feed with webhook enabled."""
        with patch('feed_processor.webhook.WebhookManager.batch_send') as mock_send:
            mock_send.return_value = [
                WebhookResponse(success=True, status_code=200)
            ]
            
            # Add two feeds to trigger a batch
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            
            # Start processing
            self.processor.start()
            
            # Let the processor run briefly
            import time
            time.sleep(0.5)
            
            # Stop and ensure final batch is sent
            self.processor.stop()
            
            # Verify webhook was called
            mock_send.assert_called()

    def test_webhook_batch_processing(self):
        """Test that feeds are properly batched before sending."""
        with patch('feed_processor.webhook.WebhookManager.batch_send') as mock_send:
            mock_send.return_value = [
                WebhookResponse(success=True, status_code=200)
            ]
            
            # Add three feeds (should create one full batch and one partial)
            for _ in range(3):
                self.assertTrue(self.processor.add_feed(self.sample_feed))
            
            # Start and stop to process all feeds
            self.processor.start()
            import time
            time.sleep(0.5)
            self.processor.stop()
            
            # Should have been called twice (one full batch, one partial)
            self.assertEqual(mock_send.call_count, 2)

    def test_webhook_failure_handling(self):
        """Test handling of webhook failures."""
        with patch('feed_processor.webhook.WebhookManager.batch_send') as mock_send:
            # Simulate a failed webhook call
            mock_send.return_value = [
                WebhookResponse(
                    success=False,
                    status_code=500,
                    error_message="Internal Server Error",
                    retry_count=3
                )
            ]
            
            # Add feeds and process
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            
            self.processor.start()
            import time
            time.sleep(0.5)
            self.processor.stop()
            
            # Verify webhook was called and metrics were updated
            mock_send.assert_called()

    def test_rate_limiting(self):
        """Test handling of rate limiting in webhook calls."""
        with patch('feed_processor.webhook.WebhookManager.batch_send') as mock_send:
            # Simulate rate limiting
            mock_send.return_value = [
                WebhookResponse(
                    success=False,
                    status_code=429,
                    error_message="Rate limit exceeded",
                    retry_count=1,
                    rate_limited=True
                )
            ]
            
            # Add feeds and process
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            self.assertTrue(self.processor.add_feed(self.sample_feed))
            
            self.processor.start()
            import time
            time.sleep(0.5)
            self.processor.stop()
            
            # Verify webhook was called and rate limiting was handled
            mock_send.assert_called()

    def test_process_feed(self):
        """Test processing a single feed."""
        feed_data = {'type': 'rss', 'title': 'Test', 'link': 'http://example.com'}
        self.processor._process_feed(feed_data)
        self.assertEqual(len(self.processor.current_batch), 1)

if __name__ == '__main__':
    unittest.main()
