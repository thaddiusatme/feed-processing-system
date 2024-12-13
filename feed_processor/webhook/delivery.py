"""Webhook delivery system with rate limiting and retries."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import structlog

from feed_processor.metrics.prometheus import MetricsCollector


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

        self.last_delivery_time = 0
        self.metrics = MetricsCollector()
        self.logger = structlog.get_logger(__name__)

        # Track delivery status
        self.delivery_status: Dict[str, Dict[str, Any]] = {}

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between deliveries."""
        now = time.time()
        time_since_last = now - self.last_delivery_time
        if time_since_last < self.rate_limit:
            delay = self.rate_limit - time_since_last
            self.metrics.record("webhook_rate_limit_delay", delay)
            time.sleep(self.rate_limit)  # Always sleep for full delay
        self.last_delivery_time = time.time()

    def _get_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for retries.

        Args:
            attempt: Current retry attempt number

        Returns:
            Delay in seconds before next retry
        """
        delay = self.retry_delay * (2**attempt)
        return min(delay, 300)  # Cap at 5 minutes

    def deliver_batch(self, items: List[Dict[str, Any]], batch_id: Optional[str] = None) -> bool:
        """Deliver a batch of items via webhook with retries.

        Args:
            items: List of items to deliver
            batch_id: Optional identifier for the batch

        Returns:
            True if delivery was successful
        """
        if not items:
            return True

        if len(items) > self.batch_size:
            self.logger.warning(
                "webhook_batch_size_exceeded",
                actual_size=len(items),
                max_size=self.batch_size,
            )
            items = items[: self.batch_size]

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FeedProcessor-Webhook/1.0",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "batch_id": batch_id or datetime.now(timezone.utc).isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }

        for attempt in range(self.max_retries + 1):
            try:
                self._wait_for_rate_limit()
                start_time = time.time()

                response = requests.post(
                    url=self.webhook_url,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )

                delivery_time = time.time() - start_time
                self.metrics.record("webhook_delivery_time", delivery_time)

                if response.status_code == 429:  # Rate limited
                    self.metrics.increment("webhook_rate_limits")
                    delay = self._get_retry_delay(attempt)
                    self.logger.warning(
                        "webhook_rate_limited",
                        attempt=attempt,
                        delay=delay,
                    )
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                self.metrics.increment("webhook_deliveries", labels={"status": "success"})

                # Update status tracking
                self.delivery_status[payload["batch_id"]] = {
                    "status": "delivered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "items": len(items),
                    "attempts": attempt + 1,
                }

                return True

            except requests.exceptions.RequestException as e:
                self.metrics.increment("webhook_deliveries", labels={"status": "failed"})
                self.logger.error(
                    "webhook_delivery_failed",
                    error=str(e),
                    attempt=attempt,
                    batch_id=payload["batch_id"],
                )

                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    self.logger.info(
                        "webhook_delivery_retry",
                        attempt=attempt,
                        delay=delay,
                    )
                    time.sleep(delay)
                    continue

                # Update status tracking for final failure
                self.delivery_status[payload["batch_id"]] = {
                    "status": "failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "items": len(items),
                    "attempts": attempt + 1,
                    "error": str(e),
                }

                return False

        return False

    def get_delivery_status(self, batch_id: str) -> Dict[str, Any]:
        """Get the delivery status for a batch.

        Args:
            batch_id: Batch identifier

        Returns:
            Status information for the batch
        """
        return self.delivery_status.get(
            batch_id,
            {
                "status": "unknown",
                "timestamp": None,
                "items": 0,
                "attempts": 0,
            },
        )
