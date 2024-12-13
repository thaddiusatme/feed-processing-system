import threading
import time

class RateLimiter:
    """Rate limiter for controlling request frequency."""
    
    def __init__(self, requests_per_second: int = 2):
        """Initialize the rate limiter.
        
        Args:
            requests_per_second: Maximum number of requests allowed per second.
        """
        self.requests_per_second = requests_per_second
        self.interval = 1.0 / requests_per_second
        self.lock = threading.Lock()
        self.last_request_time = time.time()
    
    def wait(self) -> None:
        """Wait if necessary to maintain the rate limit."""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.interval:
                time.sleep(self.interval - time_since_last)
            
            self.last_request_time = time.time()
    
    def reset(self) -> None:
        """Reset the rate limiter state."""
        with self.lock:
            self.last_request_time = time.time()
