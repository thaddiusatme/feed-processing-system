from dataclasses import dataclass
from datetime import datetime
import time
import threading
from queue import Queue
import requests
from typing import Dict, Any, Optional, List
import random
import logging
import os

@dataclass
class ProcessingMetrics:
    processed_count: int = 0
    error_count: int = 0
    start_time: datetime = datetime.now()
    last_process_time: float = 0
    queue_length: int = 0
    
    def get_error_rate(self) -> float:
        total = self.processed_count + self.error_count
        return (self.error_count / total) * 100 if total > 0 else 0

class RateLimiter:
    def __init__(self, min_interval: float = 0.2):
        self.min_interval = min_interval
        self.last_request = 0
        self._lock = threading.Lock()
    
    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()

    def exponential_backoff(self, attempt: int):
        # Exponential backoff with jitter
        wait_time = min(2 ** attempt + random.uniform(0, 1), 60)
        time.sleep(wait_time)

from .webhook_manager import WebhookManager, WebhookResponse
from .content_queue import ContentQueue, QueuedContent

class FeedProcessingError(Exception):
    """Base exception for feed processing errors."""
    pass

class FeedProcessor:
    def __init__(
        self,
        inoreader_token: str,
        webhook_url: str,
        content_queue: Optional[ContentQueue] = None,
        webhook_manager: Optional[WebhookManager] = None,
        test_mode: bool = False
    ):
        """Initialize the feed processor.
        
        Args:
            inoreader_token: Inoreader API token
            webhook_url: URL to send processed content
            content_queue: Optional custom content queue
            webhook_manager: Optional custom webhook manager
            test_mode: If True, won't start continuous processing
        """
        self.inoreader_token = inoreader_token
        self.webhook_url = webhook_url
        self.queue = content_queue or ContentQueue()
        self.webhook_manager = webhook_manager or WebhookManager(webhook_url)
        self.metrics = ProcessingMetrics()
        self.running = False
        self.processing = False
        self.test_mode = test_mode
        self.batch_size = 10
        self.poll_interval = 60  # seconds
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = RateLimiter()
        
    def fetch_feeds(self) -> List[Dict[str, Any]]:
        """Fetch feeds from Inoreader API.
        
        Returns:
            List of feed items.
        
        Raises:
            requests.exceptions.RequestException: If API request fails.
        """
        try:
            if not self.inoreader_token:
                self.logger.error("No Inoreader token provided")
                return []

            headers = {
                "Authorization": f"Bearer {self.inoreader_token}",
                "Accept": "application/json"
            }
            response = requests.get(
                "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            # Enqueue items for processing
            for item in items:
                self.queue.enqueue(item)
            
            return items
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                self.metrics.error_count += 1
                self.logger.error("Authentication failed: Invalid or expired token. Please check your Inoreader token.")
            else:
                self.metrics.error_count += 1
                self.logger.error(f"HTTP error occurred: {e}")
            return []
            
        except requests.exceptions.RequestException as e:
            self.metrics.error_count += 1
            self.logger.error(f"Error fetching feeds: {e}")
            return []

    def detect_content_type(self, content: Dict[str, Any]) -> str:
        """Detect content type based on content signals."""
        if "social_signals" in content:
            return "SOCIAL"
        if "video_url" in content:
            return "VIDEO"
        if "image_url" in content:
            return "IMAGE"
        return "TEXT"
        
    def calculate_priority(self, content: Dict[str, Any]) -> int:
        """Calculate content priority based on various signals."""
        priority = 0
        if content.get("engagement_score", 0) > 100:
            priority += 2
        if content.get("is_trending", False):
            priority += 3
        if content.get("content_type") == "SOCIAL":
            priority += 1
        return priority
        
    def process_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single content item."""
        try:
            content_type = self.detect_content_type(item)
            priority = self.calculate_priority(item)
            
            processed_item = {
                "id": item.get("id"),
                "title": item.get("title"),
                "content": item.get("content", {}).get("content"),
                "published": item.get("published"),
                "content_type": content_type,
                "priority": priority
            }
            
            self.metrics.processed_count += 1
            return processed_item
        except Exception as e:
            self.logger.error(f"Error processing item: {str(e)}")
            self.metrics.error_count += 1
            return None
            
    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of items."""
        processed_items = []
        for item in items:
            if processed := self.process_item(item):
                processed_items.append(processed)
        return processed_items
        
    def send_to_webhook(self, data: Dict[str, Any]) -> WebhookResponse:
        """Send processed content to webhook."""
        return self.webhook_manager.send_webhook(data)
        
    def send_batch_to_webhook(self, items: List[Dict[str, Any]]) -> List[WebhookResponse]:
        """Send a batch of items to webhook."""
        return self.webhook_manager.bulk_send(items)
        
    def get_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics."""
        return self.metrics
        
    def start(self) -> None:
        """Start the feed processor."""
        if self.running:
            return
            
        self.running = True
        self.processing = True
        
        if not self.test_mode:
            self.process_thread = threading.Thread(target=self._process_loop)
            self.process_thread.daemon = True
            self.process_thread.start()
        
    def stop(self) -> None:
        """Stop the feed processor."""
        self.running = False
        self.processing = False
        
        if not self.test_mode and hasattr(self, 'process_thread'):
            self.process_thread.join(timeout=5.0)
                
    def _process_loop(self) -> None:
        """Main processing loop."""
        while self.running:
            try:
                # Fetch new items
                items = self.fetch_feeds()
                
                # Process items in batches
                for i in range(0, len(items), self.batch_size):
                    batch = items[i:i + self.batch_size]
                    processed_batch = self.process_batch(batch)
                    
                    if processed_batch:
                        responses = self.send_batch_to_webhook(processed_batch)
                        for response in responses:
                            if not response.success:
                                self.logger.error(f"Webhook delivery failed: {response.error_type}")
                                
                # Wait before next processing cycle
                threading.Event().wait(self.poll_interval)
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
                time.sleep(1)  # Avoid tight loop on persistent errors