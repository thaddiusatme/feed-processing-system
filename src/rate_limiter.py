import threading
import time
from typing import Optional


class RateLimiter:
    """
    Thread-safe rate limiter that ensures a minimum interval between operations.

    Args:
        min_interval (float): Minimum time interval (in seconds) between operations.
    """

    def __init__(self, min_interval: float = 0.2):
        self.min_interval = min_interval
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
