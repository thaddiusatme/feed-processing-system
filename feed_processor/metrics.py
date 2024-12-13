from prometheus_client import Counter, Gauge, Histogram, start_http_server
import threading

# Initialize metrics
PROCESSING_RATE = Counter(
    'feed_processing_rate',
    'Number of feeds processed per second'
)

QUEUE_SIZE = Gauge(
    'feed_queue_size',
    'Current number of items in the processing queue'
)

PROCESSING_LATENCY = Histogram(
    'feed_processing_latency_seconds',
    'Time taken to process each feed',
    buckets=[.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0]
)

WEBHOOK_RETRIES = Counter(
    'feed_webhook_retries_total',
    'Number of webhook delivery retry attempts'
)

WEBHOOK_PAYLOAD_SIZE = Histogram(
    'feed_webhook_payload_size_bytes',
    'Size of webhook payloads in bytes',
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
)

RATE_LIMIT_DELAY = Gauge(
    'feed_rate_limit_delay_seconds',
    'Current rate limit delay being applied'
)

QUEUE_OVERFLOWS = Counter(
    'feed_queue_overflows_total',
    'Number of times the queue has overflowed'
)

# Queue distribution by feed type
QUEUE_DISTRIBUTION = Gauge(
    'feed_queue_distribution',
    'Distribution of items in queue by feed type',
    ['feed_type']
)

def start_metrics_server(port=8000):
    """Start the Prometheus metrics server on the specified port."""
    start_http_server(port)
    print(f"Metrics server started on port {port}")

# Start metrics server in a separate thread
def init_metrics():
    metrics_thread = threading.Thread(
        target=start_metrics_server,
        args=(8000,),
        daemon=True
    )
    metrics_thread.start()
