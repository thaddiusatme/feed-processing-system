from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Tuple
import threading
import statistics

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
        self.value += amount
        self.last_updated = datetime.now(timezone.utc)
    
    def decrement(self, amount: int = 1) -> None:
        self.value -= amount
        self.last_updated = datetime.now(timezone.utc)
    
    def reset(self) -> None:
        self.value = 0
        self.last_updated = datetime.now(timezone.utc)

@dataclass
class Gauge(Metric):
    """Gauge metric for current value measurements."""
    value: float = 0.0
    
    def set(self, value: float) -> None:
        self.value = value
        self.last_updated = datetime.now(timezone.utc)
    
    def reset(self) -> None:
        self.value = 0.0
        self.last_updated = datetime.now(timezone.utc)

@dataclass
class Histogram(Metric):
    """Histogram metric for tracking value distributions."""
    values: List[float] = field(default_factory=list)
    
    @property
    def count(self) -> int:
        return len(self.values)
    
    @property
    def min(self) -> Optional[float]:
        return min(self.values) if self.values else None
    
    @property
    def max(self) -> Optional[float]:
        return max(self.values) if self.values else None
    
    @property
    def average(self) -> Optional[float]:
        return statistics.mean(self.values) if self.values else None
    
    def record(self, value: float) -> None:
        self.values.append(value)
        self.last_updated = datetime.now(timezone.utc)
    
    def reset(self) -> None:
        self.values.clear()
        self.last_updated = datetime.now(timezone.utc)

class MetricsCollector:
    """Thread-safe collector for various types of metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, Dict[str, Metric]] = {}
        self._lock = threading.Lock()
    
    def _get_metric_key(self, name: str, labels: Dict[str, str]) -> str:
        """Generate unique key for a metric based on name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"
    
    def _ensure_metric(
        self,
        name: str,
        metric_type: MetricType,
        labels: Dict[str, str]
    ) -> Metric:
        """Create metric if it doesn't exist."""
        key = self._get_metric_key(name, labels)
        
        if key not in self._metrics:
            if metric_type == MetricType.COUNTER:
                self._metrics[key] = Counter(name, metric_type, labels)
            elif metric_type == MetricType.GAUGE:
                self._metrics[key] = Gauge(name, metric_type, labels)
            elif metric_type == MetricType.HISTOGRAM:
                self._metrics[key] = Histogram(name, metric_type, labels)
        
        metric = self._metrics[key]
        if metric.type != metric_type:
            raise ValueError(
                f"Metric '{name}' already exists with different type: {metric.type}"
            )
        
        return metric
    
    def increment(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            metric = self._ensure_metric(
                name,
                MetricType.COUNTER,
                labels or {}
            )
            if not isinstance(metric, Counter):
                raise ValueError(f"Metric '{name}' is not a counter")
            metric.increment(value)
    
    def decrement(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Decrement a counter metric."""
        with self._lock:
            metric = self._ensure_metric(
                name,
                MetricType.COUNTER,
                labels or {}
            )
            if not isinstance(metric, Counter):
                raise ValueError(f"Metric '{name}' is not a counter")
            metric.decrement(value)
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value."""
        with self._lock:
            metric = self._ensure_metric(
                name,
                MetricType.GAUGE,
                labels or {}
            )
            if not isinstance(metric, Gauge):
                raise ValueError(f"Metric '{name}' is not a gauge")
            metric.set(value)
    
    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a value in a histogram metric."""
        with self._lock:
            metric = self._ensure_metric(
                name,
                MetricType.HISTOGRAM,
                labels or {}
            )
            if not isinstance(metric, Histogram):
                raise ValueError(f"Metric '{name}' is not a histogram")
            metric.record(value)
    
    def get_metric(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Metric:
        """Get a metric by name and labels."""
        key = self._get_metric_key(name, labels or {})
        with self._lock:
            if key not in self._metrics:
                raise KeyError(f"Metric not found: {key}")
            return self._metrics[key]
    
    def reset(self) -> None:
        """Reset all metrics to their initial state."""
        with self._lock:
            for metric in self._metrics.values():
                metric.reset()
    
    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get current state of all metrics."""
        snapshot = {}
        with self._lock:
            for key, metric in self._metrics.items():
                metric_data = {
                    "type": metric.type.value,
                    "labels": metric.labels,
                    "last_updated": metric.last_updated.isoformat()
                }
                
                if isinstance(metric, Counter):
                    metric_data["value"] = metric.value
                elif isinstance(metric, Gauge):
                    metric_data["value"] = metric.value
                elif isinstance(metric, Histogram):
                    metric_data.update({
                        "count": metric.count,
                        "min": metric.min,
                        "max": metric.max,
                        "average": metric.average
                    })
                
                snapshot[metric.name] = metric_data
        
        return snapshot
    
    def batch_update(
        self,
        updates: Dict[str, Tuple[str, Union[int, float]]]
    ) -> None:
        """Update multiple metrics at once.
        
        Args:
            updates: Dict mapping metric names to (operation, value) tuples.
                    Operations: "increment", "gauge", "record"
        """
        for name, (operation, value) in updates.items():
            if operation == "increment":
                with self._lock:
                    metric = self._ensure_metric(name, MetricType.COUNTER, {})
                    if isinstance(metric, Counter):
                        metric.increment(int(value))
            elif operation == "gauge":
                with self._lock:
                    metric = self._ensure_metric(name, MetricType.GAUGE, {})
                    if isinstance(metric, Gauge):
                        metric.set(float(value))
            elif operation == "record":
                with self._lock:
                    metric = self._ensure_metric(name, MetricType.HISTOGRAM, {})
                    if isinstance(metric, Histogram):
                        metric.record(float(value))
            else:
                raise ValueError(f"Unknown operation: {operation}")

def start_metrics_server(port=8000):
    """Start a Prometheus metrics server on the specified port."""
    from prometheus_client import start_http_server
    start_http_server(port)

def init_metrics(port=8000):
    """Initialize and start the metrics server on the specified port."""
    metrics_thread = threading.Thread(
        target=start_metrics_server,
        args=(port,),
        daemon=True
    )
    metrics_thread.start()
