"""Prometheus metrics exporter for the feed processing system."""

import time
from typing import Any, Dict

import structlog
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from prometheus_client.core import CollectorRegistry

logger = structlog.get_logger(__name__)


class PrometheusExporter:
    """Export metrics in Prometheus format."""

    def __init__(self, port: int = 8000):
        """Initialize the Prometheus exporter.

        Args:
            port: Port to expose metrics on
        """
        self.port = port
        self.registry = CollectorRegistry()

        # Processing metrics
        self.items_processed = Counter(
            "feed_items_processed_total",
            "Total number of feed items processed",
            ["status"],
            registry=self.registry,
        )
        self.queue_size = Gauge(
            "feed_queue_size",
            "Current size of the processing queue",
            ["priority"],
            registry=self.registry,
        )
        self.processing_latency = Histogram(
            "feed_processing_latency_seconds",
            "Feed processing latency in seconds",
            registry=self.registry,
        )

        # API metrics
        self.api_requests = Counter(
            "feed_api_requests_total",
            "Total number of API requests",
            ["status"],
            registry=self.registry,
        )
        self.api_latency = Histogram(
            "feed_api_latency_seconds", "API request latency in seconds", registry=self.registry
        )

        # Webhook metrics
        self.webhook_requests = Counter(
            "feed_webhook_requests_total",
            "Total number of webhook requests",
            ["status"],
            registry=self.registry,
        )
        self.webhook_retries = Counter(
            "feed_webhook_retries_total",
            "Total number of webhook retry attempts",
            registry=self.registry,
        )
        self.webhook_latency = Histogram(
            "feed_webhook_latency_seconds",
            "Webhook request latency in seconds",
            registry=self.registry,
        )
        self.rate_limit_delay = Gauge(
            "feed_rate_limit_delay_seconds",
            "Current rate limit delay in seconds",
            registry=self.registry,
        )

        # Queue metrics
        self.queue_overflows = Counter(
            "feed_queue_overflows_total",
            "Total number of queue overflow events",
            ["priority"],
            registry=self.registry,
        )
        self.enqueued_items = Counter(
            "feed_enqueued_items_total",
            "Total number of items enqueued",
            ["priority"],
            registry=self.registry,
        )
        self.dequeued_items = Counter(
            "feed_dequeued_items_total", "Total number of items dequeued", registry=self.registry
        )

    def start(self) -> None:
        """Start the metrics server."""
        try:
            start_http_server(self.port, registry=self.registry)
            logger.info("metrics_server_started", port=self.port)
        except Exception as e:
            logger.error("metrics_server_failed", error=str(e))
            raise

    def update_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Update metrics from a snapshot.

        Args:
            snapshot: Dictionary containing current metric values
        """
        try:
            # Update processing metrics
            if "items_processed" in snapshot:
                self.items_processed.inc(snapshot["items_processed"])

            if "queue_size" in snapshot:
                for priority, size in snapshot["queue_size"].items():
                    self.queue_size.labels(priority=priority).set(size)

            if "processing_latency" in snapshot:
                self.processing_latency.observe(snapshot["processing_latency"])

            # Update webhook metrics
            if "webhook_requests" in snapshot:
                self.webhook_requests.inc(snapshot["webhook_requests"])

            if "webhook_retries" in snapshot:
                self.webhook_retries.inc(snapshot["webhook_retries"])

            if "webhook_latency" in snapshot:
                self.webhook_latency.observe(snapshot["webhook_latency"])

            if "rate_limit_delay" in snapshot:
                self.rate_limit_delay.set(snapshot["rate_limit_delay"])

            logger.debug("metrics_updated", snapshot=snapshot)
        except Exception as e:
            logger.error("metrics_update_failed", error=str(e), snapshot=snapshot)
            raise
