"""Prometheus metrics implementation for feed processing system."""

import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """Base class for all metric types."""

    name: str
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Counter(Metric):
    """Counter metric for counting events or items."""

    value: int = 0

    def increment(self, amount: int = 1) -> None:
        """Increment counter by specified amount."""
        self.value += amount
        self.last_updated = datetime.now(timezone.utc)

    def decrement(self, amount: int = 1) -> None:
        """Decrement counter by specified amount."""
        self.value -= amount
        self.last_updated = datetime.now(timezone.utc)

    def reset(self) -> None:
        """Reset counter to zero."""
        self.value = 0
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class Gauge(Metric):
    """Gauge metric for current value measurements."""

    value: float = 0.0

    def set(self, value: float) -> None:
        """Set gauge to specified value."""
        self.value = value
        self.last_updated = datetime.now(timezone.utc)

    def reset(self) -> None:
        """Reset gauge to zero."""
        self.value = 0.0
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class Histogram(Metric):
    """Histogram metric for tracking value distributions."""

    values: List[float] = field(default_factory=list)
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 2.0, 5.0])

    def count(self) -> int:
        """Get number of recorded values."""
        return len(self.values)

    def min(self) -> float:
        """Get minimum recorded value."""
        return min(self.values) if self.values else 0.0

    def max(self) -> float:
        """Get maximum recorded value."""
        return max(self.values) if self.values else 0.0

    def average(self) -> float:
        """Get average of recorded values."""
        return statistics.mean(self.values) if self.values else 0.0

    def percentile(self, p: float) -> float:
        """Get percentile value.

        Args:
            p: Percentile (0-100)

        Returns:
            Value at specified percentile
        """
        if not self.values:
            return 0.0
        return statistics.quantiles(self.values, n=100)[int(p)-1]

    def record(self, value: float) -> None:
        """Record a new value.

        Args:
            value: Value to record
        """
        self.values.append(value)
        self.last_updated = datetime.now(timezone.utc)

    def reset(self) -> None:
        """Reset histogram to empty state."""
        self.values = []
        self.last_updated = datetime.now(timezone.utc)


class MetricsCollector:
    """Thread-safe collector for various types of metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self._metrics: Dict[str, Dict[str, Metric]] = {}
        self._lock = threading.Lock()

    def _get_metric_key(self, name: str, labels: Dict[str, str]) -> str:
        """Generate unique key for a metric based on name and labels.

        Args:
            name: Metric name
            labels: Metric labels

        Returns:
            Unique metric key
        """
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"

    def _ensure_metric(
        self, name: str, metric_type: MetricType, labels: Dict[str, str]
    ) -> None:
        """Create metric if it doesn't exist.

        Args:
            name: Metric name
            metric_type: Type of metric
            labels: Metric labels
        """
        key = self._get_metric_key(name, labels)
        if key not in self._metrics.get(name, {}):
            if name not in self._metrics:
                self._metrics[name] = {}

            if metric_type == MetricType.COUNTER:
                self._metrics[name][key] = Counter(name, metric_type, labels)
            elif metric_type == MetricType.GAUGE:
                self._metrics[name][key] = Gauge(name, metric_type, labels)
            elif metric_type == MetricType.HISTOGRAM:
                self._metrics[name][key] = Histogram(name, metric_type, labels)

    def increment(
        self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Amount to increment by
            labels: Optional metric labels
        """
        with self._lock:
            self._ensure_metric(name, MetricType.COUNTER, labels or {})
            key = self._get_metric_key(name, labels or {})
            self._metrics[name][key].increment(value)

    def decrement(
        self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Decrement a counter metric.

        Args:
            name: Metric name
            value: Amount to decrement by
            labels: Optional metric labels
        """
        with self._lock:
            self._ensure_metric(name, MetricType.COUNTER, labels or {})
            key = self._get_metric_key(name, labels or {})
            self._metrics[name][key].decrement(value)

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value.

        Args:
            name: Metric name
            value: Value to set
            labels: Optional metric labels
        """
        with self._lock:
            self._ensure_metric(name, MetricType.GAUGE, labels or {})
            key = self._get_metric_key(name, labels or {})
            self._metrics[name][key].set(value)

    def record(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a value in a histogram metric.

        Args:
            name: Metric name
            value: Value to record
            labels: Optional metric labels
        """
        with self._lock:
            self._ensure_metric(name, MetricType.HISTOGRAM, labels or {})
            key = self._get_metric_key(name, labels or {})
            self._metrics[name][key].record(value)

    def get_metric(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Optional[Metric]:
        """Get a metric by name and labels.

        Args:
            name: Metric name
            labels: Optional metric labels

        Returns:
            Metric instance if found, None otherwise
        """
        with self._lock:
            if name not in self._metrics:
                return None
            key = self._get_metric_key(name, labels or {})
            return self._metrics[name].get(key)

    def reset(self) -> None:
        """Reset all metrics to their initial state."""
        with self._lock:
            for metrics in self._metrics.values():
                for metric in metrics.values():
                    metric.reset()

    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get current state of all metrics.

        Returns:
            Dictionary containing all metric values and metadata
        """
        with self._lock:
            snapshot = {}
            for name, metrics in self._metrics.items():
                snapshot[name] = {}
                for key, metric in metrics.items():
                    snapshot[name][key] = {
                        "type": metric.type.value,
                        "labels": metric.labels,
                        "last_updated": metric.last_updated.isoformat(),
                        "value": metric.value if hasattr(metric, "value") else None,
                        "values": metric.values if hasattr(metric, "values") else None,
                    }
            return snapshot

    def batch_update(
        self, updates: Dict[str, Tuple[str, Union[int, float]]]
    ) -> None:
        """Update multiple metrics at once.

        Args:
            updates: Dict mapping metric names to (operation, value) tuples.
                    Operations: "increment", "gauge", "record"
        """
        with self._lock:
            for name, (operation, value) in updates.items():
                if operation == "increment":
                    self.increment(name, int(value))
                elif operation == "gauge":
                    self.set_gauge(name, float(value))
                elif operation == "record":
                    self.record(name, float(value))


def start_metrics_server(port: int = 8000) -> None:
    """Start a Prometheus metrics server on the specified port.

    Args:
        port: Port number for metrics server
    """
    # TODO: Implement Prometheus metrics server
    pass


def init_metrics(port: int = 8000) -> None:
    """Initialize and start the metrics server on the specified port.

    Args:
        port: Port number for metrics server
    """
    start_metrics_server(port)
