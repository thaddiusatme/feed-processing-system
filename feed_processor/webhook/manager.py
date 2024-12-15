"""Webhook management module for handling outgoing webhook requests."""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import structlog

from feed_processor.error_handling import ErrorHandler
from feed_processor.metrics.prometheus import metrics
from feed_processor.webhook.delivery_manager import WebhookDeliveryManager, WebhookResponse
from feed_processor.webhook.tracing import TracingConfig, TracingManager

logger = structlog.get_logger(__name__)

__all__ = ["WebhookDeliveryManager", "WebhookResponse", "TracingManager", "TracingConfig"]


@dataclass
class WebhookError(Exception):
    """Error class for webhook-related exceptions."""

    message: str
    status_code: Optional[int] = None
    error_id: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = datetime.now(timezone.utc).isoformat()


class WebhookManager:
    """Manager class for handling webhook operations.

    This class handles sending webhooks, retrying failed requests, and tracking metrics.
    """

    def __init__(
        self,
        webhook_url: str,
        error_handler: Optional[ErrorHandler] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        batch_size: int = 50,
    ):
        """Initialize the webhook manager.

        Args:
            webhook_url: URL to send webhooks to
            error_handler: Optional error handler for processing errors
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
            batch_size: Maximum items per webhook batch
        """
        self.webhook_url = webhook_url
        self.error_handler = error_handler
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
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

    def _validate_payload(self, payload: Dict) -> bool:
        """Validate webhook payload.

        Args:
            payload: The payload to validate

        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = ["title", "contentType", "brief"]
        valid_content_types = ["BLOG"]

        # Check required fields
        if not all(field in payload for field in required_fields):
            return False

        # Validate content type
        if not any(ct in valid_content_types for ct in payload["contentType"]):
            return False

        # Validate title length
        if len(payload["title"]) > 255:
            return False

        return True

    def send_items(self, items: List[Dict]) -> List[WebhookResponse]:
        """Send items in batches.

        Args:
            items: List of items to send

        Returns:
            List[WebhookResponse]: List of responses for each batch
        """
        responses = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            response = self.send_batch(batch)
            responses.append(response)
        return responses

    def send_batch(self, items: List[Dict], retry_count: int = 0) -> WebhookResponse:
        """Send a batch of items via webhook.

        Args:
            items: List of items to send
            retry_count: Current retry attempt number

        Returns:
            WebhookResponse with delivery status
        """
        if not items:
            return WebhookResponse(success=True, status_code=200)

        # Validate payloads
        for item in items:
            if not self._validate_payload(item):
                return WebhookResponse(
                    success=False,
                    status_code=400,
                    error_type="invalid_payload",
                    error_message="Invalid payload",
                )

        self.batch_size_gauge.set(len(items))
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
                    error_message="Rate limit exceeded",
                    response_time=duration,
                )

            if response.status_code >= 500 and retry_count < self.max_retries:
                time.sleep(self.retry_delay * (2**retry_count))  # Exponential backoff
                return self.send_batch(items, retry_count + 1)

            response.raise_for_status()
            self.webhook_counter.labels(status="success").inc()

            return WebhookResponse(
                success=True,
                status_code=response.status_code,
                response_time=duration,
            )

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            self.webhook_counter.labels(status="failed").inc()

            if retry_count < self.max_retries:
                time.sleep(self.retry_delay * (2**retry_count))  # Exponential backoff
                return self.send_batch(items, retry_count + 1)

            error_type = "request_failed"
            error_message = str(e)

            return WebhookResponse(
                success=False,
                status_code=getattr(e.response, "status_code", 500),
                error_type=error_type,
                error_message=error_message,
                response_time=duration,
            )
