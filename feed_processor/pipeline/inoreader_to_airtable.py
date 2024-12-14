"""Pipeline for fetching content from Inoreader and storing in Airtable."""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import structlog
from prometheus_client import Counter, Gauge, Histogram

from feed_processor.core.clients import InoreaderClient
from feed_processor.metrics.prometheus import metrics
from feed_processor.queues.content import ContentQueue, QueuedContent
from feed_processor.storage import AirtableClient, AirtableConfig, ContentItem, ContentStatus

from ..notifications import NotificationConfig, NotificationEvent, NotificationLevel, Notifier

logger = structlog.get_logger(__name__)


class InoreaderToAirtablePipeline:
    """Pipeline to fetch from Inoreader and store in Airtable with monitoring."""

    def __init__(
        self,
        inoreader_client: InoreaderClient,
        airtable_client: AirtableClient,
        content_queue: Optional[ContentQueue] = None,
        batch_size: int = 50,
        notifier: Optional[Notifier] = None,
    ):
        """Initialize the pipeline.

        Args:
            inoreader_client: Configured Inoreader client
            airtable_client: Configured Airtable client
            content_queue: Optional custom content queue
            batch_size: Number of items to process in each batch
            notifier: Optional notifier for error alerts
        """
        self.inoreader_client = inoreader_client
        self.airtable_client = airtable_client
        self.content_queue = content_queue or ContentQueue()
        self.batch_size = batch_size
        self.notifier = notifier or Notifier()
        self.running = False

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics for monitoring."""
        metrics.register_counter(
            "pipeline_items_processed_total",
            "Total number of items processed by the pipeline",
            ["status"],
        )
        metrics.register_histogram(
            "pipeline_processing_duration_seconds",
            "Time taken to process items through the pipeline",
            ["operation"],
        )
        metrics.register_gauge(
            "pipeline_queue_size",
            "Current number of items in the processing queue",
        )

    async def fetch_and_queue_items(self) -> int:
        """Fetch items from Inoreader and add them to the processing queue.

        Returns:
            Number of items queued
        """
        items_queued = 0
        continuation = None

        while True:
            try:
                start_time = time.time()
                items = await self.inoreader_client.get_stream_contents(continuation)
                metrics.observe_histogram(
                    "pipeline_processing_duration_seconds",
                    time.time() - start_time,
                    {"operation": "fetch"},
                )

                if not items:
                    break

                # Queue items for processing
                for item in items:
                    queued_content = QueuedContent(
                        content_id=item.source_id,
                        content=item.dict(),
                        timestamp=datetime.now(timezone.utc),
                    )
                    if self.content_queue.enqueue(queued_content):
                        items_queued += 1

                metrics.increment_counter(
                    "pipeline_items_processed_total",
                    {"status": "queued"},
                    len(items),
                )
                metrics.set_gauge("pipeline_queue_size", self.content_queue.size)

                # Check if there are more items to fetch
                if len(items) < self.batch_size:
                    break

            except Exception as e:
                logger.error(
                    "error_fetching_items",
                    error=str(e),
                    continuation=continuation,
                )
                metrics.increment_counter(
                    "pipeline_items_processed_total",
                    {"status": "fetch_error"},
                )
                await self.notifier.notify(
                    NotificationEvent(
                        level=NotificationLevel.ERROR,
                        title="Feed Fetch Error",
                        message=f"Error fetching items from Inoreader: {str(e)}",
                        metadata={
                            "continuation": continuation,
                            "items_queued": items_queued,
                        },
                    )
                )
                break

        return items_queued

    async def process_and_store_batch(self) -> int:
        """Process a batch of items from the queue and store in Airtable.

        Returns:
            Number of items successfully processed and stored
        """
        processed_count = 0
        items_to_store: List[Dict] = []

        try:
            # Process items from queue
            for _ in range(self.batch_size):
                if self.content_queue.is_empty():
                    break

                queued_item = self.content_queue.dequeue()
                if not queued_item:
                    continue

                items_to_store.append(queued_item.content)
                processed_count += 1

            if items_to_store:
                start_time = time.time()
                # Store items in Airtable
                await self.airtable_client.create_records(items_to_store)
                metrics.observe_histogram(
                    "pipeline_processing_duration_seconds",
                    time.time() - start_time,
                    {"operation": "store"},
                )

                metrics.increment_counter(
                    "pipeline_items_processed_total",
                    {"status": "stored"},
                    len(items_to_store),
                )

        except Exception as e:
            logger.error(
                "error_processing_batch",
                error=str(e),
                batch_size=len(items_to_store),
            )
            metrics.increment_counter(
                "pipeline_items_processed_total",
                {"status": "store_error"},
            )
            await self.notifier.notify(
                NotificationEvent(
                    level=NotificationLevel.ERROR,
                    title="Batch Processing Error",
                    message=f"Error processing and storing batch: {str(e)}",
                    metadata={
                        "batch_size": len(items_to_store),
                        "queue_size": self.content_queue.size,
                    },
                )
            )
            # Requeue failed items with increased retry count
            for item in items_to_store:
                queued_content = QueuedContent(
                    content_id=item["source_id"],
                    content=item,
                    timestamp=datetime.now(timezone.utc),
                    retry_count=1,
                )
                self.content_queue.enqueue(queued_content)

        metrics.set_gauge("pipeline_queue_size", self.content_queue.size)
        return processed_count

    async def cleanup(self) -> None:
        """Perform cleanup operations.

        - Removes processed items older than retention period
        - Cleans up any temporary resources
        - Records cleanup metrics
        """
        try:
            start_time = time.time()
            logger.info("starting_cleanup")

            # Clean up old processed items from Airtable
            retention_days = int(os.getenv("RETENTION_DAYS", "30"))
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

            deleted_count = await self.airtable_client.delete_old_records(cutoff_date=cutoff_date)

            # Clean up the queue
            self.content_queue.clear_old_items(cutoff_date)

            metrics.observe_histogram(
                "pipeline_processing_duration_seconds",
                time.time() - start_time,
                {"operation": "cleanup"},
            )

            metrics.increment_counter(
                "pipeline_items_processed_total",
                {"status": "cleaned_up"},
                deleted_count,
            )

            logger.info(
                "cleanup_completed",
                deleted_count=deleted_count,
                retention_days=retention_days,
            )

        except Exception as e:
            logger.error(
                "cleanup_error",
                error=str(e),
            )
            metrics.increment_counter(
                "pipeline_items_processed_total",
                {"status": "cleanup_error"},
            )

    async def run(self, interval: float = 60.0) -> None:
        """Run the pipeline continuously.

        Args:
            interval: Time in seconds between fetch operations
        """
        self.running = True
        logger.info("pipeline_started", interval=interval)

        cleanup_interval = float(os.getenv("CLEANUP_INTERVAL_HOURS", "24")) * 3600
        last_cleanup = time.time()

        while self.running:
            try:
                # Run cleanup if needed
                if time.time() - last_cleanup >= cleanup_interval:
                    await self.cleanup()
                    last_cleanup = time.time()

                # Fetch new items
                items_queued = await self.fetch_and_queue_items()
                logger.info("items_queued", count=items_queued)

                # Process queued items
                while not self.content_queue.is_empty() and self.running:
                    processed_count = await self.process_and_store_batch()
                    logger.info(
                        "batch_processed",
                        count=processed_count,
                        remaining=self.content_queue.size,
                    )

                if self.running:
                    await asyncio.sleep(interval)

            except Exception as e:
                logger.error("pipeline_error", error=str(e))
                if self.running:
                    await asyncio.sleep(interval)

        logger.info("pipeline_stopped")

    def stop(self) -> None:
        """Stop the pipeline gracefully."""
        logger.info("stopping_pipeline")
        self.running = False
