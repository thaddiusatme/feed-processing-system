from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProcessingMetrics:
    """
    Tracks processing metrics for the feed processing system.
    """

    processed_count: int = 0
    error_count: int = 0
    start_time: datetime = datetime.now()
    last_process_time: float = 0
    queue_length: int = 0

    def increment_processed(self) -> None:
        """Increment the count of processed items."""
        self.processed_count += 1

    def increment_errors(self) -> None:
        """Increment the count of errors."""
        self.error_count += 1

    def update_process_time(self, process_time: float) -> None:
        """Update the last process time."""
        self.last_process_time = process_time

    def update_queue_length(self, length: int) -> None:
        """Update the current queue length."""
        self.queue_length = length
