"""Rate limiter implementation for feed processing."""

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

import structlog

from feed_processor.metrics.prometheus import MetricsCollector

logger = structlog.get_logger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration."""

    requests_per_second: float
    burst_size: Optional[int] = None
    window_size: Optional[float] = None


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation."""

    def __init__(self, rate_limit: RateLimit, metrics: MetricsCollector):
        """Initialize rate limiter.

        Args:
            rate_limit: Rate limit configuration
            metrics: Metrics collector for monitoring
        """
        self.rate = rate_limit.requests_per_second
        self.burst_size = rate_limit.burst_size or int(self.rate * 2)
        self.window_size = rate_limit.window_size or 1.0

        self.tokens = self.burst_size
        self.last_update = time.time()
        self.lock = threading.Lock()
        self.metrics = metrics

        self._update_metrics()
        logger.info(
            "rate_limiter_initialized",
            rate=self.rate,
            burst_size=self.burst_size,
            window_size=self.window_size,
        )

    def _update_metrics(self) -> None:
        """Update rate limiter metrics."""
        self.metrics.rate_limit_tokens.set(self.tokens)
        self.metrics.rate_limit_rate.set(self.rate)

    def _add_tokens(self) -> None:
        """Add tokens based on time elapsed."""
        now = time.time()
        time_passed = now - self.last_update
        new_tokens = time_passed * self.rate

        self.tokens = min(self.burst_size, self.tokens + new_tokens)
        self.last_update = now
        self._update_metrics()

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait for tokens

        Returns:
            True if tokens were acquired, False if timed out
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._add_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self._update_metrics()
                    logger.debug(
                        "tokens_acquired",
                        requested=tokens,
                        remaining=self.tokens,
                    )
                    return True

            if timeout is not None and time.time() - start_time > timeout:
                logger.warning(
                    "rate_limit_timeout",
                    requested=tokens,
                    timeout=timeout,
                )
                return False

            # Wait a fraction of the window size before trying again
            time.sleep(self.window_size / 10)

    def wait(self, tokens: int = 1) -> float:
        """Wait until tokens are available.

        Args:
            tokens: Number of tokens to wait for

        Returns:
            Time waited in seconds
        """
        start_time = time.time()

        while not self.acquire(tokens, timeout=self.window_size):
            continue

        wait_time = time.time() - start_time
        if wait_time > 0:
            logger.info(
                "rate_limit_wait",
                tokens=tokens,
                wait_time=wait_time,
            )

        return wait_time
