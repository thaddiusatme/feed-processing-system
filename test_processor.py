import unittest
import time
from unittest.mock import Mock, patch
from feed_processor.processor import FeedProcessor

class TestFeedProcessor(unittest.TestCase):
    def setUp(self):
        # Mock the metrics initialization to avoid port conflicts
        with patch('feed_processor.processor.init_metrics'):
            self.processor = FeedProcessor(max_queue_size=10)
            self.processor.start()
        
        self.sample_rss = """<?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0">
        <channel>
            <title>Sample RSS Feed</title>
            <link>http://example.com/feed</link>
            <description>A sample RSS feed for testing</description>
            <pubDate>Mon, 13 Dec 2024 03:01:14 -0800</pubDate>
        </channel>
        </rss>"""
        
    def tearDown(self):
        if self.processor.processing_thread.is_alive():
            self.processor.stop()

    def test_add_feed_success(self):
        feed_data = {'type': 'rss', 'content': self.sample_rss}
        result = self.processor.add_feed(feed_data)
        self.assertTrue(result)
        self.assertEqual(self.processor.queue.qsize(), 1)

    def test_add_feed_invalid_content(self):
        feed_data = {'type': 'rss', 'content': 'invalid content'}
        result = self.processor.add_feed(feed_data)
        self.assertFalse(result)
        self.assertEqual(self.processor.queue.qsize(), 0)

    def test_add_feed_queue_full(self):
        # Fill the queue with valid feeds
        feed_data = {'type': 'rss', 'content': self.sample_rss}
        for _ in range(10):
            self.processor.add_feed(feed_data)
        
        # Try to add one more
        result = self.processor.add_feed(feed_data)
        self.assertFalse(result)

    def test_process_feed(self):
        with patch.object(FeedProcessor, '_process_feed') as mock_process:
            feed_data = {'type': 'rss', 'content': self.sample_rss}
            self.processor.add_feed(feed_data)
            time.sleep(0.2)  # Give time for processing
            mock_process.assert_called_once()

    def test_rate_limiting(self):
        large_content = 'x' * 6000
        with patch('time.sleep') as mock_sleep:
            self.processor._process_feed({'type': 'rss', 'content': large_content})
            mock_sleep.assert_called_with(0.5)  # Check rate limit delay

    def test_webhook_retries(self):
        huge_content = 'x' * 11000
        with patch('feed_processor.processor.WEBHOOK_RETRIES.inc') as mock_inc:
            self.processor._process_feed({'type': 'rss', 'content': huge_content})
            mock_inc.assert_called_once()

if __name__ == '__main__':
    unittest.main()
