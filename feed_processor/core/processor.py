"""Core processor implementation for feed processing system."""

import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from feed_processor.core.clients.inoreader import InoreaderClient
from feed_processor.core.errors import APIError
from feed_processor.metrics.prometheus import init_metrics
from feed_processor.queues.content import ContentQueue, QueuedContent
from feed_processor.webhook.manager import WebhookManager, WebhookResponse


@dataclass
class ProcessingMetrics:
    """Represents processing metrics for the feed processor."""

    processed_count: int = 0
    error_count: int = 0
    start_time: datetime = datetime.now()
    last_process_time: float = 0
    queue_length: int = 0

    def get_error_rate(self) -> float:
        """Calculate error rate based on processed and error counts."""
        if self.processed_count == 0:
            return 0.0
        return self.error_count / self.processed_count


class RateLimiter:
    """Rate limiter class to manage API request intervals."""

    def __init__(self, min_interval: float = 0.2):
        """Initialize rate limiter with minimum interval."""
        self.min_interval = min_interval
        self.last_request = 0
        self._lock = threading.Lock()

    def wait(self):
        """Wait for the minimum interval before making the next request."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()

    def exponential_backoff(self, attempt: int):
        """Perform exponential backoff with jitter."""
        delay = min(300, self.min_interval * (2 ** attempt))  # Cap at 5 minutes
        jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
        time.sleep(delay + jitter)


class FeedProcessor:
    """Main processor class for handling feed content."""

    def __init__(
        self,
        inoreader_token: str,
        webhook_url: str,
        content_queue: Optional[ContentQueue] = None,
        webhook_manager: Optional[WebhookManager] = None,
        test_mode: bool = False,
        metrics_port: int = 8000,
    ):
        """Initialize the feed processor.

        Args:
            inoreader_token: Inoreader API token
            webhook_url: URL to send processed content
            content_queue: Optional custom content queue
            webhook_manager: Optional custom webhook manager
            test_mode: If True, won't start continuous processing
            metrics_port: Port to use for Prometheus metrics
        """
        self.inoreader_client = InoreaderClient(inoreader_token)
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
        init_metrics(metrics_port)  # Initialize Prometheus metrics with specified port

    def fetch_feeds(self) -> List[Dict[str, Any]]:
        """Fetch feeds from Inoreader API.

        Returns:
            List of feed items.

        Raises:
            APIError: If API request fails or authentication is invalid.
        """
        try:
            if not self.inoreader_client:
                self.logger.error("No Inoreader client configured")
                return []

            response = self.inoreader_client.get_unread_items()
            items = response.get("items", [])

            # Enqueue items for processing
            for item in items:
                self.queue.enqueue(item)

            return items

        except APIError as e:
            self.metrics.error_count += 1
            self.logger.error(f"API error occurred: {e}")
            return []

    def detect_content_type(self, content: Dict[str, Any]) -> str:
        """Detect content type based on content signals.

        Args:
            content: Content item to analyze

        Returns:
            String indicating content type (SOCIAL, VIDEO, NEWS, etc)
        """
        if "social_signals" in content:
            return "SOCIAL"
        if "video_url" in content:
            return "VIDEO"
        if "news_score" in content:
            return "NEWS"
        return "GENERAL"

    def calculate_priority(self, content: Dict[str, Any]) -> int:
        """Calculate content priority based on various signals.

        Args:
            content: Content item to analyze

        Returns:
            Priority score (1-10, higher is more important)
        """
        priority = 5  # Default priority

        # Boost priority based on engagement signals
        if content.get("likes", 0) > 1000:
            priority += 2
        if content.get("shares", 0) > 500:
            priority += 2

        # Adjust based on content type
        content_type = self.detect_content_type(content)
        if content_type == "NEWS":
            priority += 1
        elif content_type == "VIDEO":
            priority += 2

        # Cap priority between 1-10
        return max(1, min(priority, 10))

    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single content item.

        Args:
            item: Content item to process

        Returns:
            Processed item with additional metadata
        """
        start_time = time.time()

        try:
            # Add processing metadata
            processed_item = item.copy()
            processed_item.update({
                "processed_at": datetime.now().isoformat(),
                "content_type": self.detect_content_type(item),
                "priority": self.calculate_priority(item)
            })

            self.metrics.processed_count += 1
            self.metrics.last_process_time = time.time() - start_time

            return processed_item

        except Exception as e:
            self.metrics.error_count += 1
            self.logger.error(f"Error processing item: {e}")
            raise

    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of items.

        Args:
            items: List of content items to process

        Returns:
            List of processed items
        """
        processed_items = []
        for item in items:
            try:
                processed_item = self.process_item(item)
                processed_items.append(processed_item)
            except Exception as e:
                self.logger.error(f"Failed to process item in batch: {e}")
                continue
        return processed_items

    def send_batch_to_webhook(self, items: List[Dict[str, Any]]) -> bool:
        """Send a batch of items to webhook.

        Args:
            items: List of processed items to send

        Returns:
            True if delivery was successful
        """
        if not items:
            return True

        try:
            response = self.webhook_manager.deliver_batch(items)
            if not response.success:
                self.logger.error(f"Webhook delivery failed: {response.error}")
                self.metrics.error_count += 1
                return False
            return True

        except Exception as e:
            self.logger.error(f"Error sending to webhook: {e}")
            self.metrics.error_count += 1
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics.

        Returns:
            Dictionary of current metrics
        """
        return {
            "processed_count": self.metrics.processed_count,
            "error_count": self.metrics.error_count,
            "error_rate": self.metrics.get_error_rate(),
            "queue_length": self.queue.size(),
            "uptime_seconds": (datetime.now() - self.metrics.start_time).total_seconds(),
            "last_process_time": self.metrics.last_process_time
        }

    def start(self):
        """Start the feed processor."""
        if self.running:
            self.logger.warning("Feed processor is already running")
            return

        self.running = True
        if not self.test_mode:
            threading.Thread(target=self._process_loop, daemon=True).start()

    def stop(self):
        """Stop the feed processor."""
        self.running = False
        self.processing = False

    def _process_loop(self):
        """Main processing loop."""
        self.processing = True
        while self.running:
            try:
                # Fetch new items
                items = self.fetch_feeds()
                if items:
                    self.logger.info(f"Fetched {len(items)} new items")

                # Process items in batches
                while not self.queue.empty() and self.running:
                    batch = []
                    for _ in range(self.batch_size):
                        if self.queue.empty():
                            break
                        batch.append(self.queue.dequeue())

                    if batch:
                        processed_batch = self.process_batch(batch)
                        self.send_batch_to_webhook(processed_batch)

                if self.running:
                    time.sleep(self.poll_interval)

            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                self.metrics.error_count += 1
                time.sleep(5)  # Wait before retrying

        self.processing = False
