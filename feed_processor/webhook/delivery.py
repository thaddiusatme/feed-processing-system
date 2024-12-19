"""Webhook delivery system with rate limiting and retries."""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import structlog

from feed_processor.metrics.prometheus import metrics
from feed_processor.webhook.rate_limiter import EndpointRateLimiter, RateLimitConfig


@dataclass
class WebhookResponse:
    """Response from a webhook delivery attempt."""

    success: bool
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_after: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookDeliverySystem:
    """Handles reliable webhook delivery with rate limiting and retries."""

    def __init__(
        self,
        webhook_url: str,
        auth_token: Optional[str] = None,
        rate_limit: float = 0.2,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        batch_size: int = 10,
    ):
        """Initialize the webhook delivery system.

        Args:
            webhook_url: URL to deliver webhooks to
            auth_token: Optional authentication token
            rate_limit: Minimum seconds between requests
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
            batch_size: Maximum items per webhook delivery
        """
        self.webhook_url = webhook_url
        self.auth_token = auth_token
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.logger = structlog.get_logger(__name__)

        # Initialize rate limiter
        config = RateLimitConfig(requests_per_second=1.0 / rate_limit)
        self.rate_limiter = EndpointRateLimiter(default_config=config)

        # Extract endpoint from webhook URL for rate limiting
        parsed_url = urlparse(webhook_url)
        self.endpoint = f"{parsed_url.netloc}{parsed_url.path}"

        # Track delivery status
        self.delivery_status: Dict[str, Dict[str, Any]] = {}

        # Initialize metrics
        self.delivery_counter = metrics.register_counter(
            "webhook_deliveries_total", "Total number of webhook deliveries", ["status"]
        )
        self.delivery_latency = metrics.register_histogram(
            "webhook_delivery_duration_seconds", "Duration of webhook deliveries"
        )
        self.batch_size_gauge = metrics.register_gauge(
            "webhook_batch_size", "Current webhook batch size"
        )
        self.retry_counter = metrics.register_counter(
            "webhook_retries_total", "Total number of webhook delivery retries"
        )

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between deliveries."""
        wait_time = self.rate_limiter.acquire(self.endpoint)
        if wait_time > 0:
            time.sleep(wait_time)

    def deliver_batch(self, items: List[Dict[str, Any]], retry_count: int = 0) -> bool:
        """Deliver a batch of items via webhook.

        Args:
            items: List of items to deliver
            retry_count: Current retry attempt number

        Returns:
            True if delivery was successful
        """
        if not items:
            return True

        self.batch_size_gauge.set(len(items))
        start_time = time.time()

        try:
            self._wait_for_rate_limit()

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "FeedProcessor/1.0",
            }
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            response = requests.post(
                self.webhook_url,
                json={"items": items},
                headers=headers,
                timeout=30,
            )

            duration = time.time() - start_time
            self.delivery_latency.observe(duration)

            if response.status_code == 429:  # Rate limited
                self.delivery_counter.labels(status="rate_limited").inc()
                if retry_count < self.max_retries:
                    self.retry_counter.inc()
                    time.sleep(self.retry_delay * (2**retry_count))
                    return self.deliver_batch(items, retry_count + 1)
                return False

            response.raise_for_status()
            self.delivery_counter.labels(status="success").inc()
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(
                "webhook_delivery_failed",
                error=str(e),
                retry_count=retry_count,
                items_count=len(items),
            )
            self.delivery_counter.labels(status="failed").inc()

            if retry_count < self.max_retries:
                self.retry_counter.inc()
                time.sleep(self.retry_delay * (2**retry_count))
                return self.deliver_batch(items, retry_count + 1)

            return False

    def deliver_items(self, items: List[Dict[str, Any]]) -> bool:
        """Deliver items in batches respecting size limits.

        Args:
            items: List of items to deliver

        Returns:
            True if all batches were delivered successfully
        """
        if not items:
            return True

        success = True
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            if not self.deliver_batch(batch):
                success = False
                break

        return success
