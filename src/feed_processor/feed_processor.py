import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import structlog

from .error_handling import ErrorCategory, ErrorHandler, ErrorSeverity
from .metrics import MetricsCollector
from .priority_queue import Priority, PriorityQueue, QueueItem
from .webhook_manager import WebhookManager


class FeedProcessor:
    """Main processor for handling feed items from Inoreader.

    This class orchestrates the entire feed processing pipeline, including:
    - Fetching feed items from Inoreader API with pagination support
    - Processing and validating feed items
    - Priority-based queueing of items
    - Reliable webhook delivery with retries
    - Comprehensive error handling and logging

    The processor uses a priority queue to ensure important items (like breaking news)
    are processed first, while maintaining efficient memory usage through queue size limits.

    Attributes:
        inoreader_token (str): Authentication token for Inoreader API
        queue (PriorityQueue): Thread-safe priority queue for feed items
        webhook_manager (WebhookManager): Manages webhook delivery with rate limiting
        error_handler (ErrorHandler): Handles errors with circuit breaker pattern
        logger (structlog.BoundLogger): Structured logger for the processor
        metrics (MetricsCollector): Collects metrics for feed processing performance
    """

    def __init__(
        self,
        inoreader_token: str,
        webhook_url: str,
        queue_size: int = 1000,
        webhook_rate_limit: float = 0.2,
    ) -> None:
        """Initialize the feed processor.

        Args:
            inoreader_token: API token for Inoreader authentication
            webhook_url: Endpoint URL for webhook delivery
            queue_size: Maximum number of items in the priority queue (default: 1000)
            webhook_rate_limit: Minimum seconds between webhook calls (default: 0.2)

        Raises:
            ValueError: If inoreader_token or webhook_url is empty
        """
        if not inoreader_token or not webhook_url:
            raise ValueError("Inoreader token and webhook URL are required")

        self.inoreader_token = inoreader_token
        self.webhook_url = webhook_url
        self.queue = PriorityQueue(queue_size)
        self.webhook_manager = WebhookManager(webhook_url, webhook_rate_limit)
        self.error_handler = ErrorHandler()
        self.metrics = MetricsCollector()
        self._initialize_metrics()

        # Setup structured logging
        self.logger = structlog.get_logger(__name__).bind(
            component="FeedProcessor", webhook_url=webhook_url, queue_size=queue_size
        )
        self.logger.info("feed_processor_initialized")

    def _initialize_metrics(self):
        """Initialize metrics for tracking feed processing performance."""
        # Processing metrics
        self.metrics.increment("items_processed", 0, labels={"status": "success"})
        self.metrics.increment("items_processed", 0, labels={"status": "failed"})
        self.metrics.set_gauge("queue_size", 0)
        self.metrics.record("processing_latency", 0.0)

        # API metrics
        self.metrics.increment("api_requests", 0, labels={"status": "success"})
        self.metrics.increment("api_requests", 0, labels={"status": "failed"})

        # Webhook metrics
        self.metrics.increment("webhook_deliveries", 0, labels={"status": "success"})
        self.metrics.increment("webhook_deliveries", 0, labels={"status": "failed"})

    def _fetch_feeds(self, continuation: Optional[str] = None) -> Dict[str, Any]:
        """Fetch feed items from Inoreader API with pagination support.

        This method handles the low-level API interaction with Inoreader,
        including error handling and response validation.

        Args:
            continuation: Pagination token from previous API response

        Returns:
            Dict containing feed items and pagination info, or empty dict on error

        Note:
            The response includes a 'continuation' token for pagination and
            an 'items' list containing the feed entries.
        """
        url = "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list"
        headers = {
            "Authorization": f"Bearer {self.inoreader_token}",
            "Content-Type": "application/json",
        }
        params = {"n": 100}  # Fetch 100 items at a time

        if continuation:
            params["c"] = continuation

        response = None
        try:
            start_time = time.time()
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            self.metrics.record("api_latency", time.time() - start_time)
            self.metrics.increment("api_requests", labels={"status": "success"})
            return response.json()
        except Exception as e:
            self.metrics.increment("api_requests", labels={"status": "failed"})
            self.error_handler.handle_error(
                error=e,
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service="inoreader",
                details={
                    "url": url,
                    "params": params,
                    "response_status": getattr(response, "status_code", None),
                    "response_text": getattr(response, "text", None),
                },
            )
            return {}

    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate a single feed item.

        This method transforms raw feed items into a standardized format,
        validates required fields, and handles various edge cases.

        Args:
            item: Raw feed item from Inoreader API

        Returns:
            Processed item with standardized fields, or empty dict if validation fails

        The processed item includes:
            - id: Unique identifier
            - title: Item title
            - author: Content author (optional)
            - content: Main content body
            - url: Canonical URL
            - published: ISO format timestamp
            - categories: List of category labels
            - processed_at: Processing timestamp
        """
        try:
            # Validate required fields
            if not all(key in item for key in ["id", "title", "summary"]):
                raise ValueError("Missing required fields")

            # Validate nested fields
            if not isinstance(item.get("summary"), dict):
                raise ValueError("Invalid summary format")
            if not isinstance(item.get("canonical"), list) or not item.get("canonical"):
                raise ValueError("Invalid canonical URL format")

            return {
                "id": item["id"],
                "title": item["title"],
                "author": item.get("author", ""),
                "content": item["summary"].get("content", ""),
                "url": item["canonical"][0].get("href", ""),
                "published": datetime.fromtimestamp(
                    item.get("published", 0), tz=timezone.utc
                ).isoformat(),
                "categories": [cat.get("label", "") for cat in item.get("categories", [])],
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            self.error_handler.handle_error(
                error=e,
                category=ErrorCategory.PROCESSING_ERROR,
                severity=ErrorSeverity.MEDIUM,
                service="feed_processor",
                details={"item": item},
            )
            return {}

    def fetch_and_queue_items(self) -> int:
        """Fetch items from Inoreader and add them to the priority queue.

        This method orchestrates the entire fetch-process-queue pipeline:
        1. Fetches items from Inoreader with pagination
        2. Processes each item into standardized format
        3. Determines priority based on content
        4. Adds items to priority queue

        Returns:
            Number of items successfully queued

        Note:
            Items are queued based on priority, with high-priority items
            potentially displacing lower priority items when queue is full.
        """
        items_queued = 0
        continuation = None

        while True:
            response = self._fetch_feeds(continuation)
            if not response:
                break

            items = response.get("items", [])
            if not items:
                break

            for item in items:
                processed_item = self._process_item(item)
                if not processed_item:
                    continue

                # Determine priority based on item attributes
                priority = self._determine_priority(processed_item)

                queue_item = QueueItem(
                    id=processed_item["id"],
                    priority=priority,
                    content=processed_item,
                    timestamp=datetime.now(timezone.utc),
                )

                try:
                    if self.queue.enqueue(queue_item):
                        items_queued += 1
                except Exception as e:
                    self.error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.SYSTEM_ERROR,
                        severity=ErrorSeverity.HIGH,
                        service="feed_processor",
                        details={"queue_item": queue_item},
                    )

            continuation = response.get("continuation")
            if not continuation:
                break

        self.metrics.set_gauge("queue_size", self.queue.size)
        self.logger.info("items_queued", count=items_queued, queue_size=self.queue.size)
        return items_queued

    def _determine_priority(self, item: Dict[str, Any]) -> Priority:
        """Determine priority of a feed item based on its attributes.

        This method implements the priority determination logic:
        - HIGH: Breaking news items
        - NORMAL: Items published today
        - LOW: Older items

        Args:
            item: Processed feed item with standardized fields

        Returns:
            Priority level (HIGH, NORMAL, or LOW)

        Note:
            Priority rules can be customized by subclassing FeedProcessor
            and overriding this method.
        """
        # Example priority rules - customize based on requirements
        if any(cat.lower() == "breaking news" for cat in item["categories"]):
            return Priority.HIGH
        elif datetime.fromisoformat(item["published"]) > datetime.now(timezone.utc).replace(
            hour=0, minute=0
        ):
            return Priority.NORMAL
        return Priority.LOW

    def process_queue(self, batch_size: int = 10) -> int:
        """Process items from the queue and deliver via webhook.

        This method:
        1. Dequeues items in priority order
        2. Delivers items via webhook with retries
        3. Handles delivery failures with error tracking

        Args:
            batch_size: Maximum number of items to process (default: 10)

        Returns:
            Number of items successfully processed and delivered

        Note:
            Processing stops when either batch_size is reached or queue is empty.
            Failed deliveries are logged but not requeued.
        """
        processed_count = 0
        try:
            items = []
            for _ in range(batch_size):
                if self.queue.is_empty():
                    break
                items.append(self.queue.dequeue())

            if items:
                start_time = time.time()
                success = self.webhook_manager.send_webhook(
                    payload=[item.content for item in items], retries=3
                )
                processing_time = time.time() - start_time
                self.metrics.record("processing_latency", processing_time)

                if success:
                    self.metrics.increment(
                        "items_processed", len(items), labels={"status": "success"}
                    )
                    self.metrics.increment("webhook_deliveries", 1, labels={"status": "success"})
                else:
                    self.metrics.increment(
                        "items_processed", len(items), labels={"status": "failed"}
                    )
                    self.metrics.increment("webhook_deliveries", 1, labels={"status": "failed"})

                processed_count = len(items)

            self.metrics.set_gauge("queue_size", self.queue.size)
            self.logger.info(
                "batch_processed", processed_count=processed_count, remaining_items=self.queue.size
            )
            return processed_count
        except Exception as e:
            self.metrics.increment("items_processed", len(items), labels={"status": "failed"})
            self.error_handler.handle_error(
                error=e,
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.HIGH,
                service="feed_processor",
                details={"queue_size": self.queue.size},
            )
            raise
