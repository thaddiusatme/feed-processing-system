"""Processing metrics collection and reporting."""

import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .metrics.prometheus import metrics


class ProcessingMetrics:
    """Collects and reports processing metrics."""

    def __init__(self):
        """Initialize processing metrics."""
        self.processing_duration = metrics.register_histogram(
            "feed_processing_duration_seconds",
            "Duration of feed processing operations",
            ["operation"],
        )
        self.items_processed = metrics.register_counter(
            "feed_items_processed_total", "Total number of feed items processed", ["status"]
        )
        self.processing_errors = metrics.register_counter(
            "feed_processing_errors_total", "Total number of processing errors", ["error_type"]
        )
        self.batch_size = metrics.register_gauge(
            "feed_processing_batch_size", "Current processing batch size"
        )

    def track_duration(self, operation: str) -> Callable:
        """Decorator to track duration of processing operations.

        Args:
            operation: Name of the operation being tracked

        Returns:
            Callable: Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.processing_duration.labels(operation=operation).observe(
                        time.time() - start_time
                    )
                    return result
                except Exception as e:
                    self.processing_errors.labels(error_type=type(e).__name__).inc()
                    raise

            return wrapper

        return decorator

    def record_processed_item(self, status: str = "success"):
        """Record a processed item.

        Args:
            status: Processing status (success/failed)
        """
        self.items_processed.labels(status=status).inc()

    def record_error(self, error_type: str):
        """Record a processing error.

        Args:
            error_type: Type of error encountered
        """
        self.processing_errors.labels(error_type=error_type).inc()

    def set_batch_size(self, size: int):
        """Set the current batch size.

        Args:
            size: Current batch size
        """
        self.batch_size.set(size)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics values.

        Returns:
            Dict[str, Any]: Current metrics values
        """
        return {
            "items_processed": self.items_processed._value.get(),
            "processing_errors": self.processing_errors._value.get(),
            "batch_size": self.batch_size._value.get(),
        }
