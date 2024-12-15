"""Feed processor module.

This module provides the core functionality for processing RSS/Atom feeds
and storing content in Airtable. It handles content queue management,
processing, validation, and error handling.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from feed_processor.content_queue import ContentQueue, QueueItem
from feed_processor.database import Database
from feed_processor.error_handling import ErrorHandler
from feed_processor.metrics.metrics import (
    ITEMS_PROCESSED,
    PROCESSING_LATENCY,
    PROCESSING_RATE,
    QUEUE_SIZE,
)
from feed_processor.storage.airtable_client import AirtableClient, AirtableConfig
from feed_processor.storage.models import ContentItem, ContentType

logger = logging.getLogger(__name__)


class FeedProcessor:
    """A class for processing RSS/Atom feeds and storing content in Airtable.

    This class handles the core feed processing logic, including:
    - Fetching items from a content queue
    - Processing and validating content
    - Storing processed items in Airtable
    - Handling errors and metrics

    Attributes:
        content_queue (ContentQueue): Queue for managing content items
        db (Database): Database connection for persistence
        airtable_client (AirtableClient): Client for Airtable operations
        error_handler (ErrorHandler): Handler for processing errors
        batch_size (int): Number of items to process in each batch
        processing_interval (int): Time between processing batches in seconds
    """

    def __init__(
        self,
        content_queue: ContentQueue,
        db: Database,
        airtable_config: AirtableConfig,
        error_handler: ErrorHandler,
        batch_size: int = 10,
        processing_interval: int = 60,
    ):
        """Initialize the FeedProcessor.

        Args:
            content_queue: Queue for managing content items
            db: Database connection for persistence
            airtable_config: Configuration for Airtable client
            error_handler: Handler for processing errors
            batch_size: Number of items to process in each batch
            processing_interval: Time between processing batches in seconds
        """
        self.content_queue = content_queue
        self.db = db
        self.airtable_client = AirtableClient(
            api_key=airtable_config.api_key,
            base_id=airtable_config.base_id,
            table_name=airtable_config.table_name,
        )
        self.error_handler = error_handler
        self.batch_size = batch_size
        self.processing_interval = processing_interval

    async def start(self) -> None:
        """Start the feed processing loop."""
        logger.info("Starting feed processor...")
        while True:
            try:
                await self._process_batch()
                await asyncio.sleep(self.processing_interval)
            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}")
                self.error_handler.handle_error("processing_loop", e)
                await asyncio.sleep(self.processing_interval)

    async def _process_batch(self) -> None:
        """Process a batch of items from the content queue."""
        start_time = time.time()
        items = await self._get_batch()

        if not items:
            logger.debug("No items to process")
            return

        try:
            processed_items = await self._process_items(items)
            await self._store_items(processed_items)

            # Update metrics
            batch_time = time.time() - start_time
            PROCESSING_LATENCY.observe(batch_time)
            PROCESSING_RATE.inc(len(processed_items))
            ITEMS_PROCESSED.inc(len(processed_items))

        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            self.error_handler.handle_error("batch_processing", e)
            raise

    async def _get_batch(self) -> List[QueueItem]:
        """Fetch a batch of items from the content queue.

        Returns:
            List of queue items to process
        """
        try:
            items = []
            for _ in range(self.batch_size):
                item = await self.content_queue.get()
                if item is None:
                    break
                items.append(item)

            QUEUE_SIZE.set(self.content_queue.size())
            return items
        except Exception as e:
            logger.error(f"Error getting batch from queue: {str(e)}")
            self.error_handler.handle_error("queue_fetch", e)
            raise

    async def _process_items(self, items: List[QueueItem]) -> List[ContentItem]:
        """Process a list of queue items into content items.

        Args:
            items: List of queue items to process

        Returns:
            List of processed content items
        """
        processed_items = []
        for item in items:
            try:
                processed_item = await self._process_item(item)
                if processed_item:
                    processed_items.append(processed_item)
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {str(e)}")
                self.error_handler.handle_error("item_processing", e)
                continue
        return processed_items

    async def _process_item(self, item: QueueItem) -> Optional[ContentItem]:
        """Process a single queue item into a content item.

        Args:
            item: Queue item to process

        Returns:
            Processed content item or None if processing fails
        """
        try:
            if not self._validate_item(item):
                logger.warning(f"Invalid item {item.id}, skipping")
                return None

            content_item = ContentItem(
                id=item.id,
                title=item.title,
                content=item.content,
                url=item.url,
                published_at=item.published_at or datetime.now(timezone.utc),
                content_type=self._determine_content_type(item),
                metadata=self._extract_metadata(item),
            )

            return content_item
        except Exception as e:
            logger.error(f"Error processing item {item.id}: {str(e)}")
            self.error_handler.handle_error("item_processing", e)
            return None

    def _validate_item(self, item: QueueItem) -> bool:
        """Validate a queue item.

        Performs basic validation checks to ensure the queue item contains
        all required fields and data.

        Args:
            item: Queue item to validate

        Returns:
            True if item is valid, False otherwise
        """
        required_fields = [item, item.id, item.title, item.content, item.url]
        return all(required_fields)

    def _determine_content_type(self, item: QueueItem) -> ContentType:
        """Determine the content type of a queue item.

        Args:
            item: Queue item to analyze

        Returns:
            Determined content type
        """
        # This is a placeholder implementation
        return ContentType.ARTICLE

    def _extract_metadata(self, item: QueueItem) -> Dict[str, Any]:
        """Extract metadata from a queue item.

        Args:
            item: Queue item to extract metadata from

        Returns:
            Dictionary of metadata
        """
        return {
            "word_count": len(item.content.split()),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _store_items(self, items: List[ContentItem]) -> None:
        """Store processed items in Airtable.

        Args:
            items: List of content items to store
        """
        if not items:
            return

        try:
            await self.airtable_client.store_items(items)
            logger.info(f"Stored {len(items)} items in Airtable")
        except Exception as e:
            logger.error(f"Error storing items in Airtable: {str(e)}")
            self.error_handler.handle_error("airtable_storage", e)
            raise
