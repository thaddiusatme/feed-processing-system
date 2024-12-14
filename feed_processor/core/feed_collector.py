"""Core feed collection implementation."""
import asyncio
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import structlog
from prometheus_client import Counter, Gauge
from pydantic import BaseModel, HttpUrl

from feed_processor.inoreader.client import InoreaderClient, InoreaderConfig
from feed_processor.storage.models import ContentItem, ContentStatus, ContentType, SourceMetadata
from feed_processor.storage.sqlite_storage import SQLiteConfig, SQLiteStorage

logger = structlog.get_logger(__name__)


class FeedCollectorConfig(BaseModel):
    """Configuration for feed collector."""

    inoreader: InoreaderConfig
    storage: SQLiteConfig
    collection_interval: float = 60.0  # seconds


class FeedCollector:
    """Core feed collection implementation."""

    def __init__(self, config: FeedCollectorConfig):
        """Initialize feed collector.

        Args:
            config: Feed collector configuration
        """
        self.config = config
        self.client = InoreaderClient(config.inoreader)
        self.storage = SQLiteStorage(config.storage)
        self.running = False

        # Initialize metrics
        self.items_total = Counter(
            "feed_collector_items_total", "Total number of items collected", ["status"]
        )
        self.collector_running = Gauge(
            "feed_collector_running", "Whether the feed collector is running"
        )

    def _detect_content_type(self, url: str) -> ContentType:
        """Detect content type from URL."""
        domain = urlparse(url).netloc.lower()

        if any(
            vid_domain in domain for vid_domain in ["youtube.com", "vimeo.com", "dailymotion.com"]
        ):
            return ContentType.VIDEO
        elif any(
            social_domain in domain
            for social_domain in ["twitter.com", "linkedin.com", "facebook.com", "instagram.com"]
        ):
            return ContentType.SOCIAL
        return ContentType.BLOG

    async def start(self):
        """Start the feed collection process."""
        if self.running:
            logger.warning("Feed collector already running")
            return

        self.running = True
        self.collector_running.set(1)
        logger.info("Starting feed collector")

        try:
            while self.running:
                try:
                    await self.collect_feeds()
                except Exception as e:
                    logger.error("Error collecting feeds", error=str(e))
                    self.storage.log_error("collection_error", str(e))

                await asyncio.sleep(self.config.collection_interval)
        finally:
            self.running = False
            self.collector_running.set(0)

    def stop(self):
        """Stop the feed collection process."""
        logger.info("Stopping feed collector")
        self.running = False

    async def collect_feeds(self, continuation: Optional[str] = None):
        """Collect feeds from Inoreader.

        Args:
            continuation: Continuation token for pagination
        """
        items = await self.client.get_stream_contents(continuation)

        for raw_item in items:
            try:
                # Extract URL and detect content type
                url = raw_item["canonical"][0]["href"]
                content_type = self._detect_content_type(url)

                # Create content item
                item = ContentItem(
                    title=raw_item["title"],
                    contentType=content_type,
                    brief=raw_item.get("summary", {}).get("content", "")[:2000],
                    sourceMetadata=SourceMetadata(
                        feedId=raw_item["id"],
                        originalUrl=url,
                        publishDate=datetime.fromtimestamp(raw_item["published"], tz=timezone.utc),
                        author=raw_item.get("author"),
                        tags=[tag["label"] for tag in raw_item.get("tags", [])],
                    ),
                )

                if not self.storage.is_duplicate(str(item.sourceMetadata.originalUrl)):
                    if self.storage.store_item(item):
                        self.items_total.labels(status="success").inc()
                        logger.debug("Stored item", url=url)
                    else:
                        self.items_total.labels(status="error").inc()
                        logger.error("Failed to store item", url=url)
                else:
                    self.items_total.labels(status="duplicate").inc()
                    logger.debug("Skipped duplicate item", url=url)
            except Exception as e:
                logger.error(
                    "Error processing item", error=str(e), item_id=raw_item.get("id", "unknown")
                )
                self.storage.log_error("item_processing_error", str(e))
