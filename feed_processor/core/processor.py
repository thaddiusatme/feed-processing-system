"""Core processor implementation for feed processing system."""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from feed_processor.config.processor_config import ProcessorConfig
from feed_processor.core.clients.inoreader import InoreaderClient
from feed_processor.core.errors import APIError, ProcessingError
from feed_processor.metrics.prometheus import MetricsCollector, Counter, Gauge, Histogram
from feed_processor.queues.content import ContentQueue, QueuedContent
from feed_processor.webhook.manager import WebhookManager, WebhookResponse


@dataclass
class ProcessingMetrics:
    """Represents processing metrics for the feed processor."""

    processed_count: int = 0
    error_count: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now())
    last_process_time: float = 0.0
    queue_length: int = 0
    processed_items: Set[str] = field(default_factory=set)

    def get_error_rate(self) -> float:
        """Calculate error rate based on processed and error counts."""
        if self.processed_count == 0:
            return 0.0
        return self.error_count / self.processed_count

    def has_processed(self, item_id: str) -> bool:
        """Check if an item has been processed.

        Args:
            item_id: ID of the item to check

        Returns:
            True if the item has been processed
        """
        return item_id in self.processed_items

    def mark_processed(self, item_id: str) -> None:
        """Mark an item as processed.

        Args:
            item_id: ID of the item to mark
        """
        self.processed_items.add(item_id)
        if len(self.processed_items) > 10000:  # Prevent unbounded growth
            old_items = sorted(self.processed_items)[:5000]
            self.processed_items = set(old_items[5000:])


class RateLimiter:
    """Rate limiter class to manage API request intervals."""

    def __init__(self, min_interval: float = 0.2, max_retries: int = 3):
        """Initialize rate limiter.

        Args:
            min_interval: Minimum interval between requests in seconds
            max_retries: Maximum number of retry attempts
        """
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Wait for the minimum interval before making the next request."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()

    def exponential_backoff(self, attempt: int) -> None:
        """Perform exponential backoff with jitter.

        Args:
            attempt: Current retry attempt number
        """
        if attempt >= self.max_retries:
            raise ProcessingError("Maximum retry attempts exceeded")
        
        delay = min(300, self.min_interval * (2 ** attempt))  # Cap at 5 minutes
        jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
        time.sleep(delay + jitter)


class FeedProcessor:
    """Main processor class for handling feed content."""

    def __init__(
        self,
        inoreader_token: str,
        webhook_url: str,
        config: Optional[ProcessorConfig] = None,
        content_queue: Optional[ContentQueue] = None,
        webhook_manager: Optional[WebhookManager] = None,
    ):
        """Initialize the feed processor.

        Args:
            inoreader_token: Inoreader API token
            webhook_url: URL to send processed content
            config: Optional processor configuration
            content_queue: Optional custom content queue
            webhook_manager: Optional custom webhook manager
        """
        self.config = config or ProcessorConfig()
        self.inoreader_client = InoreaderClient(inoreader_token)
        self.webhook_url = webhook_url
        self.queue = content_queue or ContentQueue()
        self.webhook_manager = webhook_manager or WebhookManager(webhook_url)
        self.metrics = ProcessingMetrics()
        self.metrics_collector = MetricsCollector()
        self.running = False
        self.processing = False
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = RateLimiter(
            min_interval=0.2,
            max_retries=self.config.max_retries
        )

        # Initialize Prometheus metrics
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        self.metrics_collector.register(
            "feed_processor_processed_total",
            "counter",
            "Total number of processed items"
        )
        self.metrics_collector.register(
            "feed_processor_errors_total",
            "counter",
            "Total number of processing errors"
        )
        self.metrics_collector.register(
            "feed_processor_queue_length",
            "gauge",
            "Current length of processing queue"
        )
        self.metrics_collector.register(
            "feed_processor_process_time",
            "histogram",
            "Time taken to process items",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
        )

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

            # Filter out already processed items
            new_items = [
                item for item in items
                if not self.metrics.has_processed(item.get("id", ""))
            ]

            # Update metrics
            self.metrics_collector.increment(
                "feed_processor_processed_total",
                len(new_items)
            )

            # Enqueue new items for processing
            for item in new_items:
                self.queue.enqueue(item)
                self.metrics.mark_processed(item.get("id", ""))

            return new_items

        except APIError as e:
            self.metrics.error_count += 1
            self.metrics_collector.increment("feed_processor_errors_total")
            self.logger.error(f"API error occurred: {e}")
            return []

    def detect_content_type(self, content: Dict[str, Any]) -> str:
        """Detect content type based on content signals.

        Args:
            content: Content item to analyze

        Returns:
            String indicating content type (SOCIAL, VIDEO, NEWS, etc)
        """
        # Check for video content first as it's often most engaging
        if any(key in content for key in ["video_url", "youtube_id", "vimeo_id"]):
            return "VIDEO"
        
        # Check for social media signals
        if any(key in content for key in ["social_signals", "likes", "shares"]):
            return "SOCIAL"
        
        # Check for news content
        if any(key in content for key in ["news_score", "article_text"]):
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
        likes = content.get("likes", 0)
        shares = content.get("shares", 0)
        comments = content.get("comments", 0)

        if likes > 1000:
            priority += 1
        if likes > 5000:
            priority += 1

        if shares > 500:
            priority += 1
        if shares > 2000:
            priority += 1

        if comments > 100:
            priority += 1

        # Adjust based on content type
        content_type = self.detect_content_type(content)
        type_weights = {
            "VIDEO": 2,
            "NEWS": 1,
            "SOCIAL": 1,
            "GENERAL": 0
        }
        priority += type_weights.get(content_type, 0)

        # Adjust based on freshness
        published_time = content.get("published", 0)
        if published_time:
            try:
                published = datetime.fromtimestamp(published_time)
                age_hours = (datetime.now() - published).total_seconds() / 3600
                if age_hours < 1:
                    priority += 2
                elif age_hours < 6:
                    priority += 1
            except (ValueError, TypeError):
                pass

        # Cap priority between 1-10
        return max(1, min(priority, 10))

    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single content item.

        Args:
            item: Content item to process

        Returns:
            Processed item with additional metadata

        Raises:
            ProcessingError: If processing fails
        """
        start_time = time.time()

        try:
            # Add processing metadata
            processed_item = item.copy()
            processed_item.update({
                "processed_at": datetime.now().isoformat(),
                "content_type": self.detect_content_type(item),
                "priority": self.calculate_priority(item),
                "processor_version": "2.0.0"
            })

            # Update metrics
            process_time = time.time() - start_time
            self.metrics.processed_count += 1
            self.metrics.last_process_time = process_time
            self.metrics_collector.record(
                "feed_processor_process_time",
                process_time
            )

            return processed_item

        except Exception as e:
            self.metrics.error_count += 1
            self.metrics_collector.increment("feed_processor_errors_total")
            self.logger.error(f"Error processing item: {e}")
            raise ProcessingError(f"Failed to process item: {e}")

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
            except ProcessingError as e:
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
                self.metrics_collector.increment("feed_processor_errors_total")
                return False
            return True

        except Exception as e:
            self.logger.error(f"Error sending to webhook: {e}")
            self.metrics.error_count += 1
            self.metrics_collector.increment("feed_processor_errors_total")
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
            "last_process_time": self.metrics.last_process_time,
            "prometheus_metrics": self.metrics_collector.get_snapshot()
        }

    def start(self) -> None:
        """Start the feed processor."""
        if self.running:
            self.logger.warning("Feed processor is already running")
            return

        self.running = True
        if not self.config.test_mode:
            threading.Thread(target=self._process_loop, daemon=True).start()

    def stop(self) -> None:
        """Stop the feed processor."""
        self.running = False
        self.processing = False

    def _process_loop(self) -> None:
        """Main processing loop."""
        self.processing = True
        retry_count = 0

        while self.running:
            try:
                # Update queue length metric
                self.metrics_collector.set_gauge(
                    "feed_processor_queue_length",
                    self.queue.size()
                )

                # Fetch new items
                items = self.fetch_feeds()
                if items:
                    self.logger.info(f"Fetched {len(items)} new items")
                    retry_count = 0  # Reset retry count on successful fetch

                # Process items in batches
                while not self.queue.empty() and self.running:
                    batch = []
                    for _ in range(self.config.batch_size):
                        if self.queue.empty():
                            break
                        batch.append(self.queue.dequeue())

                    if batch:
                        processed_batch = self.process_batch(batch)
                        if not self.send_batch_to_webhook(processed_batch):
                            # Re-queue failed items
                            for item in processed_batch:
                                self.queue.enqueue(item)

                if self.running:
                    time.sleep(self.config.poll_interval)

            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                self.metrics.error_count += 1
                self.metrics_collector.increment("feed_processor_errors_total")
                
                # Apply exponential backoff
                try:
                    self.rate_limiter.exponential_backoff(retry_count)
                    retry_count += 1
                except ProcessingError:
                    self.logger.error("Maximum retries exceeded, stopping processor")
                    self.stop()
                    break
