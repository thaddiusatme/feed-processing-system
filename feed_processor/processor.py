"""Feed processor module for handling feed items."""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from .content_queue import ContentQueue, QueueItem
from .error_handling import ErrorHandler
from .metrics import (
    ITEMS_PROCESSED,
    PROCESSING_LATENCY,
    PROCESSING_RATE,
    QUEUE_OVERFLOWS,
    QUEUE_SIZE,
)
from .metrics.prometheus import metrics

logger = structlog.get_logger(__name__)


class FeedProcessor:
    """Processes feed items with metrics tracking."""

    def __init__(
        self,
        error_handler: Optional[ErrorHandler] = None,
        max_batch_size: int = 50,
        processing_interval: float = 1.0,
    ):
        """Initialize the feed processor.

        Args:
            error_handler: Optional error handler for processing errors
            max_batch_size: Maximum items to process in a batch
            processing_interval: Interval between processing batches
        """
        self.error_handler = error_handler
        self.max_batch_size = max_batch_size
        self.processing_interval = processing_interval
        self.queue = ContentQueue()

        # Initialize metrics using predefined metrics
        self.processing_duration = metrics.register_histogram(
            PROCESSING_LATENCY.name, PROCESSING_LATENCY.description
        )
        self.items_processed = metrics.register_counter(
            ITEMS_PROCESSED.name, ITEMS_PROCESSED.description, ITEMS_PROCESSED.labels
        )
        self.queue_size = metrics.register_gauge(QUEUE_SIZE.name, QUEUE_SIZE.description)
        self.processing_rate = metrics.register_gauge(
            PROCESSING_RATE.name, PROCESSING_RATE.description
        )
        self.queue_overflows = metrics.register_counter(
            QUEUE_OVERFLOWS.name, QUEUE_OVERFLOWS.description
        )

    def add_item(self, item: Dict[str, Any]) -> bool:
        """Add an item to the processing queue.

        Args:
            item: Item to add to the queue

        Returns:
            bool: True if item was added successfully
        """
        queue_item = QueueItem(
            id=str(item.get("id", time.time())),
            content=item,
            timestamp=datetime.now(),
        )
        success = self.queue.add(queue_item)
        if not success:
            self.queue_overflows.inc()
        self.queue_size.set(len(self.queue))
        return success

    def process_batch(self, items: List[QueueItem]) -> List[QueueItem]:
        """Process a batch of items.

        Args:
            items: List of items to process

        Returns:
            List[QueueItem]: Successfully processed items
        """
        if not items:
            return []

        start_time = time.time()
        processed_items = []

        try:
            for item in items:
                try:
                    # Process the item (implement your processing logic here)
                    processed_items.append(item)
                    self.items_processed.labels(status="success").inc()
                except Exception as e:
                    self.items_processed.labels(status="failed").inc()
                    if self.error_handler:
                        self.error_handler.handle_error(e)
                    logger.error("item_processing_failed", error=str(e), item_id=item.id)

            duration = time.time() - start_time
            self.processing_duration.observe(duration)
            if duration > 0:
                self.processing_rate.set(len(processed_items) / duration)

            return processed_items

        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(e)
            logger.error("batch_processing_failed", error=str(e))
            return processed_items

    def process_queue(self) -> List[QueueItem]:
        """Process items in the queue.

        Returns:
            List[QueueItem]: Successfully processed items
        """
        items = []
        processed_items = []

        while len(self.queue) > 0 and len(items) < self.max_batch_size:
            item = self.queue.get_next()
            if item:
                items.append(item)

        if items:
            processed_items = self.process_batch(items)
            time.sleep(self.processing_interval)

        self.queue_size.set(len(self.queue))
        return processed_items

    def clear_queue(self):
        """Clear all items from the queue."""
        self.queue.clear()
        self.queue_size.set(0)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics values.

        Returns:
            Dict[str, Any]: Current metrics values
        """
        return {
            "items_processed": self.items_processed._value.get(),
            "processing_duration": self.processing_duration._sum.get(),
            "queue_size": self.queue_size._value.get(),
            "processing_rate": self.processing_rate._value.get(),
            "queue_overflows": self.queue_overflows._value.get(),
        }
