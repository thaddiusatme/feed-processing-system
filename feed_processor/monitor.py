from datetime import datetime, timedelta
import asyncio
from typing import Dict, Optional

class FeedMonitor:
    """Monitor feeds and manage their processing schedule based on a detection window."""
    
    def __init__(self, detection_window_minutes: int = 5, rate_limit_seconds: float = 0.2):
        """
        Initialize the FeedMonitor.
        
        Args:
            detection_window_minutes: Time window in minutes to wait before rechecking a feed
            rate_limit_seconds: Minimum time in seconds between processing feeds
        """
        self.detection_window_minutes = detection_window_minutes
        self.rate_limit_seconds = rate_limit_seconds
        self.last_check_times: Dict[str, datetime] = {}
        self.last_process_time: Optional[datetime] = None
    
    def should_check_feed(self, feed_url: str) -> bool:
        """
        Determine if a feed should be checked based on the detection window.
        
        Args:
            feed_url: URL of the feed to check
            
        Returns:
            bool: True if the feed should be checked, False otherwise
        """
        if feed_url not in self.last_check_times:
            return True
            
        last_check = self.last_check_times[feed_url]
        time_since_check = datetime.now() - last_check
        return time_since_check.total_seconds() >= (self.detection_window_minutes * 60)
    
    async def process_feed(self, feed_url: str, metrics) -> None:
        """
        Process a feed while respecting rate limits.
        
        Args:
            feed_url: URL of the feed to process
            metrics: Metrics collector for monitoring
        """
        if self.last_process_time:
            time_since_last = datetime.now() - self.last_process_time
            if time_since_last.total_seconds() < self.rate_limit_seconds:
                await asyncio.sleep(
                    self.rate_limit_seconds - time_since_last.total_seconds()
                )
        
        self.last_process_time = datetime.now()
        self.last_check_times[feed_url] = self.last_process_time
        
        metrics.increment_feed_checks(feed_url)
        metrics.record_check_timestamp(feed_url)
    
    def get_feed_stats(self, feed_url: str) -> Dict:
        """
        Get statistics about a feed's processing history.
        
        Args:
            feed_url: URL of the feed
            
        Returns:
            Dict containing feed statistics
        """
        stats = {
            "last_check_time": self.last_check_times.get(feed_url),
            "checks_in_window": 1 if feed_url in self.last_check_times else 0
        }
        return stats
