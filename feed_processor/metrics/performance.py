from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter

def track_performance(func):
    """Decorator to track performance metrics of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        try:
            result = func(*args, **kwargs)
            if hasattr(args[0], 'metrics'):
                args[0].metrics.increment_processed()
            return result
        except Exception as e:
            if hasattr(args[0], 'metrics'):
                args[0].metrics.increment_errors()
            raise e
        finally:
            if hasattr(args[0], 'metrics'):
                duration = perf_counter() - start_time
                args[0].metrics.update_process_time(duration)
    
    return wrapper

@dataclass
class ProcessingMetrics:
    """Metrics for tracking feed processing performance."""
    
    processed_count: int = 0
    error_count: int = 0
    queue_length: int = 0
    start_time: datetime = datetime.now(timezone.utc)
    last_process_time: float = 0.0
    
    def increment_processed(self) -> None:
        """Increment the count of successfully processed items."""
        self.processed_count += 1
    
    def increment_errors(self) -> None:
        """Increment the count of processing errors."""
        self.error_count += 1
    
    def update_process_time(self, duration: float) -> None:
        """Update the time taken to process the last item."""
        self.last_process_time = duration
        
    def update_queue_length(self, length: int) -> None:
        """Update the current queue length."""
        self.queue_length = length
    
    @property
    def success_rate(self) -> float:
        """Calculate the success rate of processing."""
        total = self.processed_count + self.error_count
        if total == 0:
            return 0.0
        return (self.processed_count / total) * 100
    
    @property
    def processing_duration(self) -> float:
        """Calculate the total processing duration in seconds."""
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.processed_count = 0
        self.error_count = 0
        self.queue_length = 0
        self.start_time = datetime.now(timezone.utc)
        self.last_process_time = 0.0
