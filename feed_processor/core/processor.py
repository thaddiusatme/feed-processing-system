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
from feed_processor.metrics.prometheus import metrics
from feed_processor.queues.content import ContentQueue, QueuedContent
from feed_processor.webhook.manager import WebhookManager, WebhookResponse


@dataclass
class ProcessingMetrics:
    """Represents processing metrics for the feed processor."""

    items_processed: int = 0
    items_failed: int = 0
    items_queued: int = 0
    items_delivered: int = 0
    processing_errors: int = 0
    delivery_errors: int = 0
    last_processed: Optional[datetime] = None
    last_delivered: Optional[datetime] = None
    processing_time: float = 0.0
    delivery_time: float = 0.0
    batch_sizes: List[int] = field(default_factory=list)
    processed_items: Set[str] = field(default_factory=set)

    def add_batch_size(self, size: int) -> None:
        """Add a batch size to track."""
        self.batch_sizes.append(size)
        if len(self.batch_sizes) > 100:  # Keep last 100 batches
            self.batch_sizes.pop(0)

    def get_avg_batch_size(self) -> float:
        """Get average batch size."""
        return sum(self.batch_sizes) / len(self.batch_sizes) if self.batch_sizes else 0


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

    def wait(self):
        """Wait for the minimum interval before making the next request."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()

    def exponential_backoff(self, attempt: int):
        """Perform exponential backoff with jitter.

        Args:
            attempt: Current retry attempt number
        """
        if attempt > 0:
            delay = min(300, (2**attempt) + random.uniform(0, 0.1))
            time.sleep(delay)


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
        self.running = False
        self.processing = False
        self.logger = logging.getLogger(__name__)
        self.rate_limiter = RateLimiter(min_interval=0.2, max_retries=self.config.max_retries)

        # Initialize Prometheus metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        self.items_processed = metrics.register_counter(
            "feed_processor_items_processed_total", "Total number of items processed", ["status"]
        )
        self.processing_duration = metrics.register_histogram(
            "feed_processor_processing_duration_seconds", "Time taken to process items"
        )
        self.queue_size = metrics.register_gauge(
            "feed_processor_queue_size", "Current size of the content queue"
        )
        self.webhook_duration = metrics.register_histogram(
            "feed_processor_webhook_duration_seconds", "Time taken for webhook delivery"
        )

    def fetch_feeds(self) -> List[Dict[str, Any]]:
        """Fetch feeds from Inoreader API.

        Returns:
            List of feed items.

        Raises:
            APIError: If API request fails or authentication is invalid.
        """
        try:
            items = self.inoreader_client.get_unread_items(limit=self.config.batch_size)
            self.items_processed.labels(status="fetched").inc(len(items))
            return items
        except Exception as e:
            self.items_processed.labels(status="fetch_failed").inc()
            raise APIError(f"Failed to fetch feeds: {str(e)}")

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
        type_weights = {"VIDEO": 2, "NEWS": 1, "SOCIAL": 1, "GENERAL": 0}
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
        try:
            start_time = time.time()

            processed = {
                **item,
                "content_type": self.detect_content_type(item),
                "priority": self.calculate_priority(item),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            duration = time.time() - start_time
            self.processing_duration.observe(duration)
            self.items_processed.labels(status="processed").inc()

            return processed
        except Exception as e:
            self.items_processed.labels(status="process_failed").inc()
            raise ProcessingError(f"Failed to process item: {str(e)}")

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
                processed = self.process_item(item)
                processed_items.append(processed)
            except ProcessingError as e:
                self.logger.error(f"Error processing item: {str(e)}")
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
            start_time = time.time()
            response = self.webhook_manager.send_batch(items)
            duration = time.time() - start_time

            self.webhook_duration.observe(duration)
            self.items_processed.labels(
                status="delivered" if response.success else "delivery_failed"
            ).inc(len(items))

            return response.success
        except Exception as e:
            self.items_processed.labels(status="delivery_failed").inc(len(items))
            self.logger.error(f"Failed to deliver items to webhook: {str(e)}")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics.

        Returns:
            Dictionary of current metrics
        """
        return {
            "items_processed": self.metrics.items_processed,
            "items_failed": self.metrics.items_failed,
            "items_queued": self.metrics.items_queued,
            "items_delivered": self.metrics.items_delivered,
            "processing_errors": self.metrics.processing_errors,
            "delivery_errors": self.metrics.delivery_errors,
            "avg_batch_size": self.metrics.get_avg_batch_size(),
            "processing_time": self.metrics.processing_time,
            "delivery_time": self.metrics.delivery_time,
            "last_processed": self.metrics.last_processed,
            "last_delivered": self.metrics.last_delivered,
        }

    def start(self):
        """Start the feed processor."""
        if self.running:
            return

        self.running = True
        self.processing = True
        threading.Thread(target=self._process_loop, daemon=True).start()

    def stop(self):
        """Stop the feed processor."""
        self.running = False
        while self.processing:
            time.sleep(0.1)

    def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Update queue size metric
                self.queue_size.set(len(self.queue))

                # Fetch new items
                items = self.fetch_feeds()
                if items:
                    processed_items = self.process_batch(items)
                    if processed_items:
                        success = self.send_batch_to_webhook(processed_items)
                        if not success:
                            # If delivery fails, queue items for retry
                            for item in processed_items:
                                self.queue.add(QueuedContent(item))

                # Process queued items
                queued_items = self.queue.get_batch(self.config.batch_size)
                if queued_items:
                    success = self.send_batch_to_webhook([item.content for item in queued_items])
                    if success:
                        for item in queued_items:
                            self.queue.remove(item)

            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
                self.items_processed.labels(status="error").inc()

            # Rate limiting between iterations
            self.rate_limiter.wait()

        self.processing = False
