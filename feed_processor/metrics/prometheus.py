"""Prometheus metrics collection module."""

from enum import Enum
from typing import Any, Dict, List

from prometheus_client import Counter, Gauge, Histogram


class MetricType(Enum):
    """Types of metrics supported."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricsRegistry:
    """Registry for Prometheus metrics."""

    def __init__(self):
        """Initialize metrics registry."""
        self._metrics = {}

    def register_counter(self, name: str, description: str, labels: List[str] = None) -> Counter:
        """Register a new counter metric."""
        if name in self._metrics:
            return self._metrics[name]

        counter = Counter(name, description, labels or [])
        self._metrics[name] = counter
        return counter

    def register_gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        """Register a new gauge metric."""
        if name in self._metrics:
            return self._metrics[name]

        gauge = Gauge(name, description, labels or [])
        self._metrics[name] = gauge
        return gauge

    def register_histogram(
        self, name: str, description: str, labels: List[str] = None
    ) -> Histogram:
        """Register a new histogram metric."""
        if name in self._metrics:
            return self._metrics[name]

        histogram = Histogram(name, description, labels or [])
        self._metrics[name] = histogram
        return histogram

    def get_metric(self, name: str) -> Any:
        """Get a registered metric by name."""
        return self._metrics.get(name)


# Global metrics registry
metrics = MetricsRegistry()

# Cache metrics
metrics.register_counter("cache_hits", "Number of cache hits")
metrics.register_counter("cache_misses", "Number of cache misses")
metrics.register_counter("cache_evictions", "Number of cache evictions")
metrics.register_gauge("cache_compression_ratio", "Compression ratio of cached items")
metrics.register_gauge("cache_size_bytes", "Total size of cached items in bytes")


def start_metrics_server(port: int = 8000):
    """Start a Prometheus metrics server on the specified port.

    Args:
        port: Port number for metrics server
    """
    from prometheus_client import start_http_server

    start_http_server(port)


def init_metrics(port: int = 8000):
    """Initialize and start the metrics server on the specified port.

    Args:
        port: Port number for metrics server
    """
    start_metrics_server(port)
