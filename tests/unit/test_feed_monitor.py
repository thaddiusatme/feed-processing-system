import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from feed_processor.monitor import FeedMonitor
from feed_processor.models import FeedItem
from feed_processor.metrics import MonitorMetrics

class TestFeedMonitor:
    @pytest.fixture
    def monitor(self):
        return FeedMonitor(
            detection_window_minutes=5,
            rate_limit_seconds=0.2
        )
    
    @pytest.fixture
    def mock_metrics(self):
        return Mock(spec=MonitorMetrics)
    
    def test_feed_monitor_initialization(self, monitor):
        assert monitor.detection_window_minutes == 5
        assert monitor.rate_limit_seconds == 0.2
        assert hasattr(monitor, 'last_check_times')
    
    def test_should_check_feed_within_window(self, monitor):
        feed_url = "http://example.com/feed"
        # First check should always return True
        assert monitor.should_check_feed(feed_url) is True
        
        # Second check within 5 minutes should return False
        assert monitor.should_check_feed(feed_url) is False
    
    def test_should_check_feed_after_window(self, monitor):
        feed_url = "http://example.com/feed"
        monitor.last_check_times[feed_url] = datetime.now() - timedelta(minutes=6)
        assert monitor.should_check_feed(feed_url) is True
    
    @pytest.mark.asyncio
    async def test_process_feed_rate_limiting(self, monitor, mock_metrics):
        feed_url = "http://example.com/feed"
        start_time = datetime.now()
        
        # Process feed twice in quick succession
        await monitor.process_feed(feed_url, mock_metrics)
        second_process_time = datetime.now()
        
        # Verify rate limiting
        time_diff = (second_process_time - start_time).total_seconds()
        assert time_diff >= monitor.rate_limit_seconds
    
    @pytest.mark.asyncio
    async def test_process_feed_updates_metrics(self, monitor, mock_metrics):
        feed_url = "http://example.com/feed"
        await monitor.process_feed(feed_url, mock_metrics)
        
        mock_metrics.increment_feed_checks.assert_called_once_with(feed_url)
        mock_metrics.record_check_timestamp.assert_called_once_with(feed_url)
    
    def test_get_feed_stats(self, monitor):
        feed_url = "http://example.com/feed"
        check_time = datetime.now()
        monitor.last_check_times[feed_url] = check_time
        
        stats = monitor.get_feed_stats(feed_url)
        assert stats["last_check_time"] == check_time
        assert stats["checks_in_window"] == 1
