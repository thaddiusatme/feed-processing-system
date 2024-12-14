"""Rate limiter implementation for managing API request intervals."""

import threading
import time
from typing import Optional


class RateLimiter:
    """
    Thread-safe rate limiter that ensures a minimum interval between operations.

    Args:
        min_interval (float): Minimum time interval (in seconds) between operations.
        max_retries (int): Maximum number of retry attempts for rate-limited operations.
    """

    def __init__(self, min_interval: float = 0.2, max_retries: int = 3):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.last_request: float = 0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """
        Blocks until enough time has passed since the last request.
        Thread-safe implementation using a lock.
        """
        with self._lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request

            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)

            self.last_request = time.time()

    def exponential_backoff(self, attempt: int) -> None:
        """
        Implements exponential backoff with jitter for retries.

        Args:
            attempt: Current retry attempt number (0-based)
        """
        if attempt < 0:
            return

        # Calculate delay with exponential backoff and jitter
        delay = min(self.min_interval * (2**attempt), 60)  # Cap at 60 seconds
        jitter = delay * 0.1  # 10% jitter
        actual_delay = delay + (random.random() * jitter)

        time.sleep(actual_delay)
