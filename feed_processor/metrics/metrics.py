"""Metrics for feed processing system."""

from prometheus_client import Counter, Gauge, Histogram

# Processing metrics
PROCESSING_LATENCY = Histogram(
    "feed_processing_duration_seconds",
    "Time taken to process a feed item",
)

PROCESSING_RATE = Gauge(
    "feed_processing_rate_per_second",
    "Rate of feed items processed per second",
)

ITEMS_PROCESSED = Counter(
    "feed_items_processed_total",
    "Total number of feed items processed",
)

# Queue metrics
QUEUE_SIZE = Gauge(
    "feed_queue_size",
    "Current number of items in the feed queue",
)

QUEUE_OVERFLOWS = Counter(
    "feed_queue_overflows_total",
    "Number of times the queue has overflowed",
)

ITEMS_ADDED = Counter(
    "feed_queue_items_added_total",
    "Total number of items added to the queue",
)

ITEMS_REMOVED = Counter(
    "feed_queue_items_removed_total",
    "Total number of items removed from the queue",
)

# Webhook metrics
WEBHOOK_PAYLOAD_SIZE = Histogram(
    "webhook_payload_size_bytes",
    "Size of webhook payloads in bytes",
)

WEBHOOK_RETRIES = Counter(
    "webhook_retries_total",
    "Number of webhook delivery retries",
)

# Rate limiting metrics
RATE_LIMIT_DELAY = Gauge(
    "rate_limit_delay_seconds",
    "Current rate limit delay in seconds",
)


def start_metrics_server(port: int) -> None:
    """Start the Prometheus metrics server.

    Args:
        port: Port number to listen on
    """
    from prometheus_client import start_http_server

    start_http_server(port)
