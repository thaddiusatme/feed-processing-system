import threading
import time

import pytest

from feed_processor.rate_limiter import RateLimiter


def test_rate_limiter_initialization():
    limiter = RateLimiter(requests_per_second=2)
    assert limiter.requests_per_second == 2
    assert isinstance(limiter.lock, threading.Lock)
    assert limiter.last_request_time > 0


def test_rate_limiter_wait():
    limiter = RateLimiter(requests_per_second=2)

    # First request should not wait
    start_time = time.time()
    limiter.wait()
    elapsed = time.time() - start_time
    assert elapsed < 0.1  # Should be almost immediate

    # Second request within the same second should wait
    start_time = time.time()
    limiter.wait()
    elapsed = time.time() - start_time
    assert elapsed >= 0.5  # Should wait about 0.5 seconds


def test_rate_limiter_thread_safety():
    limiter = RateLimiter(requests_per_second=10)
    request_times = []

    def make_request():
        limiter.wait()
        request_times.append(time.time())

    # Create multiple threads to test concurrency
    threads = [threading.Thread(target=make_request) for _ in range(5)]

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Check that requests were properly spaced
    for i in range(1, len(request_times)):
        time_diff = request_times[i] - request_times[i - 1]
        assert time_diff >= 0.1  # At least 100ms between requests
