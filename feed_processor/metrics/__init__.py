"""Metrics collection and tracking for feed processing system.

This module provides metrics tracking functionality using Prometheus client,
with support for various metric types like counters, gauges, and histograms.
"""

import os
from enum import Enum, auto
from typing import Dict, List, Optional, Union

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

from .performance import track_performance
from .prometheus import init_metrics, start_metrics_server


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = auto()
    GAUGE = auto()
    HISTOGRAM = auto()


class Metric:
    """Represents a single metric with its metadata."""

    def __init__(
        self, name: str, type: MetricType, description: str, labels: Optional[List[str]] = None
    ):
        self.name = name
        self.type = type
        self.description = description
        self.labels = labels or []


# Processing metrics
PROCESSING_LATENCY = Metric(
    "feed_processing_duration_seconds",
    MetricType.HISTOGRAM,
    "Time taken to process a feed item",
)

PROCESSING_RATE = Metric(
    "feed_processing_rate_per_second", MetricType.GAUGE, "Rate of feed items processed per second"
)

ITEMS_PROCESSED = Metric(
    "feed_items_processed_total",
    MetricType.COUNTER,
    "Total number of feed items processed",
    ["status"],
)

QUEUE_SIZE = Metric(
    "feed_queue_size", MetricType.GAUGE, "Current number of items in the feed queue"
)

QUEUE_OVERFLOWS = Metric(
    "feed_queue_overflows_total", MetricType.COUNTER, "Total number of queue overflow events"
)


class MetricsCollector:
    """Collects and manages metrics for feed processing system."""

    def __init__(self):
        """Initialize metrics collector with default values."""
        self.metrics = {}

    def register_metric(
        self, name: str, type: MetricType, description: str, labels: Optional[List[str]] = None
    ):
        """Register a new metric."""
        metric = Metric(name, type, description, labels)
        self.metrics[name] = metric
        return metric


class CacheMetrics:
    """Metrics for content cache performance and behavior.

    Tracks cache hits, misses, evictions, compression ratios, and errors.
    """

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        """Initialize cache metrics.

        Args:
            registry: Prometheus registry to use for metrics
        """
        # Check if metrics already exist in registry
        existing_metrics = [name for name in registry._names_to_collectors.keys()]

        def create_counter(name: str, help_text: str) -> Counter:
            if name not in existing_metrics:
                return Counter(name, help_text, registry=registry)
            return registry._names_to_collectors[name]

        def create_gauge(name: str, help_text: str) -> Gauge:
            if name not in existing_metrics:
                return Gauge(name, help_text, registry=registry)
            return registry._names_to_collectors[name]

        self.cache_hits = create_counter("cache_hits_total", "Number of cache hits")
        self.cache_misses = create_counter("cache_misses_total", "Number of cache misses")
        self.cache_evictions = create_counter(
            "cache_evictions_total", "Number of cache entries evicted"
        )
        self.cache_errors = create_counter("cache_errors_total", "Number of cache operation errors")
        self.cache_compression_ratio = create_gauge(
            "cache_compression_ratio", "Ratio of compressed to uncompressed content size"
        )
        self.cache_size_bytes = create_gauge(
            "cache_size_bytes", "Total size of cached content in bytes"
        )


class FeedMetrics:
    """Metrics for feed processing operations.

    Tracks feed processing times, success/failure rates, and content sizes.
    """

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        """Initialize feed processing metrics.

        Args:
            registry: Prometheus registry to use for metrics
        """
        # Check if metrics already exist in registry
        existing_metrics = [name for name in registry._names_to_collectors.keys()]

        def create_counter(name: str, help_text: str) -> Counter:
            if name not in existing_metrics:
                return Counter(name, help_text, registry=registry)
            return registry._names_to_collectors[name]

        def create_histogram(name: str, help_text: str, buckets) -> Histogram:
            if name not in existing_metrics:
                return Histogram(name, help_text, buckets=buckets, registry=registry)
            return registry._names_to_collectors[name]

        self.feed_process_time = create_histogram(
            "feed_process_seconds", "Time spent processing feeds", buckets=(0.1, 0.5, 1.0, 2.0, 5.0)
        )
        self.feed_process_success = create_counter(
            "feed_process_success_total", "Number of successfully processed feeds"
        )
        self.feed_process_failure = create_counter(
            "feed_process_failure_total", "Number of failed feed processing attempts"
        )
        self.feed_content_size = create_histogram(
            "feed_content_bytes",
            "Size of processed feed content in bytes",
            buckets=(1000, 10000, 100000, 1000000),
        )


# Metrics registry management
_test_registry = None
_metrics = None
_feed_metrics = None


def get_registry() -> CollectorRegistry:
    """Get the appropriate metrics registry.

    Returns:
        CollectorRegistry: Registry to use for metrics
    """
    global _test_registry
    if bool(os.getenv("PYTEST_CURRENT_TEST")):
        if _test_registry is None:
            _test_registry = CollectorRegistry()
        return _test_registry
    return REGISTRY


def get_metrics() -> CacheMetrics:
    """Get the cache metrics instance.

    Returns:
        CacheMetrics: Cache metrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = CacheMetrics(registry=get_registry())
    return _metrics


def get_feed_metrics() -> FeedMetrics:
    """Get the feed metrics instance.

    Returns:
        FeedMetrics: Feed metrics instance
    """
    global _feed_metrics
    if _feed_metrics is None:
        _feed_metrics = FeedMetrics(registry=get_registry())
    return _feed_metrics


# Convenience accessors
metrics = get_metrics()
feed_metrics = get_feed_metrics()

__all__ = [
    "init_metrics",
    "start_metrics_server",
    "metrics",
    "track_performance",
    "Metric",
    "MetricType",
    "MetricsCollector",
    "PROCESSING_LATENCY",
    "PROCESSING_RATE",
    "ITEMS_PROCESSED",
    "QUEUE_SIZE",
    "QUEUE_OVERFLOWS",
    "CacheMetrics",
    "FeedMetrics",
    "get_registry",
]
