"""Webhook management module for handling outgoing webhook requests."""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
import structlog

from feed_processor.error_handling import ErrorHandler
from feed_processor.metrics.prometheus import MetricsCollector

logger = structlog.get_logger(__name__)


@dataclass
class WebhookResponse:
    """Response data for webhook deliveries."""

    success: bool
    status_code: int
    error_id: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = datetime.now(timezone.utc).isoformat()
    response_time: Optional[float] = None


class WebhookManager:
    """Manager class for handling webhook operations.

    This class handles sending webhooks, retrying failed requests, and tracking metrics.
    """

    def __init__(
        self,
        webhook_url: str,
        error_handler: ErrorHandler,
        metrics: MetricsCollector,
        rate_limit: float = 0.2,
        max_retries: int = 3,
        timeout: float = 10.0,
    ) -> None:
        """Initialize webhook manager with error handler and metrics collector."""
        self.webhook_url = webhook_url
        self.error_handler = error_handler
        self.metrics = metrics
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.last_request_time = 0
        self._lock = threading.Lock()
        self.retry_count = {}  # Track retries per webhook URL

        # Setup structured logging
        self.logger = structlog.get_logger(__name__).bind(
            component="WebhookManager",
            webhook_url=webhook_url,
            rate_limit=rate_limit,
            max_retries=max_retries,
        )
        self.logger.info("webhook_manager_initialized")

    def _initialize_metrics(self):
        """Initialize webhook delivery metrics."""
        # Initialize counters with zero values
        self.metrics.webhook_requests_total.inc(0)
        self.metrics.webhook_failures_total.inc(0)
        self.metrics.webhook_request_duration_seconds.observe(0)
        self.metrics.webhook_batch_size.set(0)

    def _validate_payload(self, payload: Dict) -> bool:
        """Validate webhook payload has required fields.

        Args:
            payload: Dictionary containing webhook data

        Returns:
            bool: True if payload is valid, False otherwise
        """
        required_fields = ["title", "brief", "contentType"]
        return all(field in payload for field in required_fields)

    def validate_payload(self, payload: Dict) -> bool:
        """
        Validate webhook payload for required fields.

        Args:
            payload: Dictionary containing webhook payload

        Returns:
            bool: True if payload is valid

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ["event_type", "data", "timestamp"]
        missing_fields = [field for field in required_fields if field not in payload]

        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            self.logger.error("webhook_payload_validation_failed", missing_fields=missing_fields)
            raise ValueError(error_msg)

        return True

    def send_webhook(self, payload: Dict) -> bool:
        """Send webhook with retry logic.

        Args:
            payload: Dictionary containing webhook data

        Returns:
            bool: True if webhook was sent successfully, False otherwise
        """
        try:
            self._validate_payload(payload)
            self.validate_payload(payload)

            retry_count = 0

            def retry_func():
                nonlocal retry_count
                retry_count += 1
                try:
                    return self._send_single_request(payload, attempt=retry_count)
                except Exception as e:
                    if retry_count >= self.max_retries:
                        raise
                    raise Exception("Retry failed") from e

            try:
                return retry_func()  # Initial attempt
            except Exception as e:
                self.error_handler.handle_error(
                    error=e,
                    category="DELIVERY_ERROR",
                    severity="MEDIUM",
                    service="webhook",
                    details={"url": self.webhook_url, "payload": payload},
                    retry_func=retry_func,
                    max_retries=self.max_retries,
                )
        except Exception as e:
            self.logger.error("Failed to send webhook", error=str(e))
            raise

    def _send_single_request(self, payload: Dict, attempt: int = 0) -> bool:
        """Send a single webhook request.

        Args:
            payload: Dictionary containing webhook data
            attempt: Current retry attempt number

        Returns:
            bool: True if request was successful, False otherwise
        """
        try:
            # Rate limit before sending
            if attempt > 0:
                backoff = (2 ** (attempt - 1)) * self.rate_limit
                time.sleep(backoff)

            # Add timestamp if not present
            if "timestamp" not in payload:
                payload["timestamp"] = datetime.now(tz=timezone.utc).isoformat()

            # Send request
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )

            # Update metrics
            self.metrics.webhook_requests_total.inc()
            self.metrics.webhook_request_duration_seconds.observe(response.elapsed.total_seconds())

            # Check response
            response.raise_for_status()

            return True

        except Exception as e:
            self.metrics.webhook_failures_total.inc()
            self.logger.error(
                "webhook_request_failed",
                error=str(e),
                attempt=attempt,
                error_type=type(e).__name__,
                error_id=str(id(e)),
            )
            raise

    def bulk_send(self, payloads: list) -> list:
        """Send multiple webhooks with rate limiting."""
        self.logger.info("starting_bulk_send", payload_count=len(payloads))

        responses = []
        success_count = 0
        error_count = 0

        for payload in payloads:
            response = self.send_webhook(payload)
            responses.append(response)

            if response:
                success_count += 1
            else:
                error_count += 1

        self.logger.info(
            "bulk_send_completed",
            total_items=len(payloads),
            success_count=success_count,
            error_count=error_count,
        )

        return responses
