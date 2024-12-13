from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from feed_processor.metrics import Metric, MetricsCollector, MetricType


@pytest.fixture
def metrics_collector():
    return MetricsCollector()


def test_counter_metric():
    """Test basic counter metric functionality."""
    collector = MetricsCollector()

    # Test increment
    collector.increment("items_processed")
    collector.increment("items_processed", 2)
    assert collector.get_metric("items_processed").value == 3

    # Test decrement
    collector.decrement("items_processed")
    assert collector.get_metric("items_processed").value == 2


def test_gauge_metric():
    """Test gauge metric for current value tracking."""
    collector = MetricsCollector()

    # Test setting values
    collector.set_gauge("queue_size", 10)
    assert collector.get_metric("queue_size").value == 10

    collector.set_gauge("queue_size", 5)
    assert collector.get_metric("queue_size").value == 5


def test_histogram_metric():
    """Test histogram for tracking value distributions."""
    collector = MetricsCollector()

    # Record processing times
    collector.record("processing_time", 0.1)
    collector.record("processing_time", 0.2)
    collector.record("processing_time", 0.3)

    histogram = collector.get_metric("processing_time")
    assert histogram.count == 3
    assert 0.1 <= histogram.average <= 0.3
    assert histogram.min == 0.1
    assert histogram.max == 0.3


def test_metric_labels():
    """Test metric labeling for better categorization."""
    collector = MetricsCollector()

    collector.increment("items_processed", labels={"priority": "high"})
    collector.increment("items_processed", labels={"priority": "low"})

    high_priority = collector.get_metric("items_processed", {"priority": "high"})
    low_priority = collector.get_metric("items_processed", {"priority": "low"})

    assert high_priority.value == 1
    assert low_priority.value == 1


def test_metric_reset():
    """Test resetting metrics to initial state."""
    collector = MetricsCollector()

    collector.increment("errors")
    collector.set_gauge("memory_usage", 100)
    collector.record("latency", 0.5)

    collector.reset()

    assert collector.get_metric("errors").value == 0
    assert collector.get_metric("memory_usage").value == 0
    assert collector.get_metric("latency").count == 0


def test_metric_snapshot():
    """Test capturing current state of all metrics."""
    collector = MetricsCollector()

    collector.increment("successes")
    collector.increment("errors")
    collector.set_gauge("queue_size", 10)
    collector.record("processing_time", 0.2)

    snapshot = collector.get_snapshot()

    assert snapshot["successes"]["value"] == 1
    assert snapshot["errors"]["value"] == 1
    assert snapshot["queue_size"]["value"] == 10
    assert snapshot["processing_time"]["average"] == 0.2


def test_invalid_metric_operations():
    """Test handling of invalid metric operations."""
    collector = MetricsCollector()

    # Can't increment a gauge
    with pytest.raises(ValueError):
        collector.increment("queue_size")
        collector.set_gauge("queue_size", 5)

    # Can't set gauge value for a counter
    with pytest.raises(ValueError):
        collector.increment("items_processed")
        collector.set_gauge("items_processed", 10)

    # Can't get non-existent metric
    with pytest.raises(KeyError):
        collector.get_metric("nonexistent")


def test_metric_timestamp():
    """Test metric timestamps for tracking when values change."""
    collector = MetricsCollector()

    before = datetime.now(timezone.utc)
    collector.increment("events")
    after = datetime.now(timezone.utc)

    metric = collector.get_metric("events")
    assert before <= metric.last_updated <= after


def test_batch_update():
    """Test updating multiple metrics at once."""
    collector = MetricsCollector()

    updates = {
        "successes": ("increment", 1),
        "queue_size": ("gauge", 10),
        "latency": ("record", 0.2),
    }

    collector.batch_update(updates)

    assert collector.get_metric("successes").value == 1
    assert collector.get_metric("queue_size").value == 10
    assert collector.get_metric("latency").average == 0.2


def test_webhook_retry_metrics():
    """Test webhook retry tracking metrics."""
    collector = MetricsCollector()

    # Test retry count increments
    collector.increment("webhook_retries", labels={"attempt": "1"})
    collector.increment("webhook_retries", labels={"attempt": "2"})
    collector.increment("webhook_retries", labels={"attempt": "1"})

    first_retry = collector.get_metric("webhook_retries", {"attempt": "1"})
    second_retry = collector.get_metric("webhook_retries", {"attempt": "2"})

    assert first_retry.value == 2
    assert second_retry.value == 1

    # Test webhook latency tracking
    collector.record("webhook_duration", 0.5)
    collector.record("webhook_duration", 1.0)

    duration = collector.get_metric("webhook_duration")
    assert duration.count == 2
    assert duration.average == 0.75
    assert duration.max == 1.0


def test_rate_limit_metrics():
    """Test rate limiting delay metrics."""
    collector = MetricsCollector()

    # Test rate limit delay tracking
    collector.set_gauge("rate_limit_delay", 30)
    assert collector.get_metric("rate_limit_delay").value == 30

    collector.set_gauge("rate_limit_delay", 60)
    assert collector.get_metric("rate_limit_delay").value == 60

    # Test rate limit hit counter
    collector.increment("rate_limit_hits")
    collector.increment("rate_limit_hits")
    assert collector.get_metric("rate_limit_hits").value == 2


def test_queue_overflow_metrics():
    """Test queue overflow tracking metrics."""
    collector = MetricsCollector()

    # Test overflow counts by priority
    collector.increment("queue_overflow", labels={"priority": "high"})
    collector.increment("queue_overflow", labels={"priority": "medium"})
    collector.increment("queue_overflow", labels={"priority": "high"})

    high_overflow = collector.get_metric("queue_overflow", {"priority": "high"})
    medium_overflow = collector.get_metric("queue_overflow", {"priority": "medium"})

    assert high_overflow.value == 2
    assert medium_overflow.value == 1

    # Test queue size by priority
    collector.set_gauge("queue_items", 5, labels={"priority": "high"})
    collector.set_gauge("queue_items", 3, labels={"priority": "medium"})

    high_items = collector.get_metric("queue_items", {"priority": "high"})
    medium_items = collector.get_metric("queue_items", {"priority": "medium"})

    assert high_items.value == 5
    assert medium_items.value == 3


def test_payload_size_metrics():
    """Test webhook payload size tracking."""
    collector = MetricsCollector()

    # Test payload size distribution
    collector.record("webhook_payload_size", 1024)  # 1KB
    collector.record("webhook_payload_size", 2048)  # 2KB
    collector.record("webhook_payload_size", 512)  # 0.5KB

    size_metric = collector.get_metric("webhook_payload_size")
    assert size_metric.count == 3
    assert size_metric.average == 1194.6666666666667  # (1024 + 2048 + 512) / 3
    assert size_metric.min == 512
    assert size_metric.max == 2048
