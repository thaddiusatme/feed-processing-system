from prometheus_client import Counter, Gauge, Histogram, start_http_server
import threading
import time

# Initialize metrics
PROCESSING_RATE = Counter("feed_processing_rate", "Number of feeds processed per second")

QUEUE_SIZE = Gauge("feed_queue_size", "Current number of items in the processing queue")

PROCESSING_LATENCY = Histogram(
    "feed_processing_latency_seconds",
    "Time taken to process each feed",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0],
)

WEBHOOK_RETRIES = Counter("feed_webhook_retries_total", "Number of webhook delivery retry attempts")

WEBHOOK_PAYLOAD_SIZE = Histogram(
    "feed_webhook_payload_size_bytes",
    "Size of webhook payloads in bytes",
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000],
)

RATE_LIMIT_DELAY = Gauge("feed_rate_limit_delay_seconds", "Current rate limit delay being applied")

QUEUE_OVERFLOWS = Counter("feed_queue_overflows_total", "Number of times the queue has overflowed")

# Queue distribution by feed type
QUEUE_DISTRIBUTION = Gauge(
    "feed_queue_distribution", "Distribution of items in queue by feed type", ["feed_type"]
)


def start_metrics_server(preferred_port=8000):
    """Start the Prometheus metrics server, trying multiple ports if necessary."""
    # Try ports in range [preferred_port, preferred_port + 100]
    for port in range(preferred_port, preferred_port + 100):
        try:
            start_http_server(port)
            print(f"Metrics server started successfully on port {port}")
            return port
        except OSError:
            print(f"Port {port} is in use, trying next port...")
            continue
    raise RuntimeError("Could not find an available port for metrics server")


def init_metrics(port=8000):
    """Initialize and start the metrics server on the specified port."""

    def run_server():
        try:
            actual_port = start_metrics_server(port)
            print(f"Metrics available at http://localhost:{actual_port}/metrics")
        except Exception as e:
            print(f"Failed to start metrics server: {e}")
            raise

    metrics_thread = threading.Thread(target=run_server, daemon=True)
    metrics_thread.start()
    # Give the server a moment to start
    time.sleep(1)
    return metrics_thread
