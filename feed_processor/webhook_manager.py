"""Webhook management module for handling outgoing webhook requests."""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import structlog

from .error_handling import ErrorHandler
from .metrics.prometheus import metrics

logger = structlog.get_logger(__name__)


@dataclass
class WebhookError(Exception):
    """Error class for webhook-related exceptions."""

    message: str
    status_code: Optional[int] = None
    error_id: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = datetime.now(timezone.utc).isoformat()


@dataclass
class WebhookResponse:
    """Response data for webhook deliveries."""

    success: bool
    status_code: int
    error_id: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = datetime.now(timezone.utc).isoformat()
    response_time: Optional[float] = None
    retry_count: Optional[int] = None


class WebhookManager:
    """Manager class for handling webhook operations.

    This class handles sending webhooks, retrying failed requests, and tracking metrics.
    """

    def __init__(
        self,
        webhook_url: str,
        error_handler: Optional[ErrorHandler] = None,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 8.0,
        retry_backoff_factor: float = 2.0,
        batch_size: int = 50,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the webhook manager.

        Args:
            webhook_url: URL to send webhooks to
            error_handler: Optional error handler for processing errors
            max_retries: Maximum number of retry attempts
            initial_retry_delay: Initial delay between retries in seconds
            max_retry_delay: Maximum delay between retries in seconds
            retry_backoff_factor: Factor to multiply delay by for each retry
            batch_size: Maximum items per webhook batch
            rate_limit: Minimum time between requests in seconds
        """
        self.webhook_url = webhook_url
        self.error_handler = error_handler
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.retry_backoff_factor = retry_backoff_factor
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.lock = threading.Lock()

        # Initialize metrics
        self.webhook_counter = metrics.register_counter(
            "webhook_requests_total", "Total number of webhook requests", ["status"]
        )
        self.webhook_latency = metrics.register_histogram(
            "webhook_request_duration_seconds", "Duration of webhook requests"
        )
        self.retry_counter = metrics.register_counter(
            "webhook_retry_attempts_total", "Total number of webhook retry attempts"
        )
        self.batch_size_gauge = metrics.register_gauge(
            "webhook_batch_size_current", "Current webhook batch size"
        )

    def send_batch(self, items: List[Dict], retry_count: int = 0) -> WebhookResponse:
        """Send a batch of items via webhook.

        Args:
            items: List of items to send
            retry_count: Current retry attempt number

        Returns:
            WebhookResponse with delivery status
        """
        if not items:
            return WebhookResponse(success=True, status_code=200, retry_count=0)

        self.batch_size_gauge.set(len(items))

        # Apply rate limiting if configured
        if self.rate_limit:
            with self.lock:
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < self.rate_limit:
                    time.sleep(self.rate_limit - time_since_last)
                self.last_request_time = time.time()

        start_time = time.time()

        try:
            response = requests.post(
                self.webhook_url,
                json={"items": items},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            duration = time.time() - start_time
            self.webhook_latency.observe(duration)

            if response.status_code == 429:  # Rate limited
                self.webhook_counter.labels(status="rate_limited").inc()
                return WebhookResponse(
                    success=False,
                    status_code=429,
                    error_type="rate_limited",
                    response_time=duration,
                    retry_count=retry_count,
                )

            if response.status_code >= 400:
                self.webhook_counter.labels(status="failed").inc()
                return WebhookResponse(
                    success=False,
                    status_code=response.status_code,
                    error_type="http_error",
                    response_time=duration,
                    retry_count=retry_count,
                )

            self.webhook_counter.labels(status="success").inc()
            return WebhookResponse(
                success=True,
                status_code=response.status_code,
                response_time=duration,
                retry_count=retry_count,
            )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            self.webhook_counter.labels(status="failed").inc()

            error_id = f"webhook_error_{int(time.time())}"
            if self.error_handler:
                self.error_handler.handle_error(e, error_id=error_id)

            return WebhookResponse(
                success=False,
                status_code=getattr(e.response, "status_code", 500),
                error_id=error_id,
                error_type="request_failed",
                response_time=duration,
                retry_count=retry_count,
            )

    def send_with_retry(self, items: List[Dict], retry_count: int = 0) -> WebhookResponse:
        """Send items with retry logic.

        Args:
            items: List of items to send
            retry_count: Current retry attempt number

        Returns:
            WebhookResponse with final delivery status
        """
        response = self.send_batch(items, retry_count)

        if not response.success and retry_count < self.max_retries:
            self.retry_counter.inc()

            # Calculate delay with exponential backoff
            delay = min(
                self.initial_retry_delay * (self.retry_backoff_factor**retry_count),
                self.max_retry_delay,
            )

            logger.info(
                "Webhook delivery failed, retrying",
                retry_count=retry_count + 1,
                max_retries=self.max_retries,
                delay=delay,
                error_type=response.error_type,
            )

            time.sleep(delay)
            return self.send_with_retry(items, retry_count + 1)

        return response

    def send_items(self, items: List[Dict]) -> List[WebhookResponse]:
        """Send items in batches with retries.

        Args:
            items: List of items to send

        Returns:
            List of WebhookResponses for each batch
        """
        if not items:
            return []

        responses = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            response = self.send_with_retry(batch)
            responses.append(response)
            if not response.success:
                break

        return responses

    def send_webhook(self, item: Dict) -> WebhookResponse:
        """Send a single item via webhook with retries.

        Args:
            item: Item to send

        Returns:
            WebhookResponse with delivery status
        """
        response = self.send_with_retry([item])
        return response
