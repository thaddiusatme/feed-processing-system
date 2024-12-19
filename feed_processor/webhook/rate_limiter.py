"""Token bucket rate limiter for webhook delivery."""

import time
from dataclasses import dataclass
from typing import Dict, Optional

import structlog

from feed_processor.metrics.prometheus import metrics


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float
    burst_size: int = 1

    @property
    def interval(self) -> float:
        """Return the interval between requests in seconds."""
        return 1.0 / self.requests_per_second


class TokenBucketRateLimiter:
    """Token bucket rate limiter implementation."""

    def __init__(
        self,
        config: RateLimitConfig,
        endpoint: Optional[str] = None,
    ):
        """Initialize the rate limiter.

        Args:
            config: Rate limit configuration
            endpoint: Optional endpoint identifier for per-endpoint limiting
        """
        self.config = config
        self.endpoint = endpoint or "default"
        self.tokens = config.burst_size
        self.last_update = time.time()
        self.logger = structlog.get_logger(__name__)

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        self.tokens_gauge = metrics.register_gauge(
            "webhook_rate_limiter_tokens",
            "Current number of tokens in the bucket",
            ["endpoint"],
        )
        self.wait_time_histogram = metrics.register_histogram(
            "webhook_rate_limiter_wait_seconds",
            "Time spent waiting for rate limit",
            ["endpoint"],
        )
        self.throttled_counter = metrics.register_counter(
            "webhook_rate_limiter_throttled_total",
            "Number of requests throttled by rate limiter",
            ["endpoint"],
        )

    def _update_tokens(self):
        """Update the token count based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(
            self.config.burst_size,
            self.tokens + elapsed * self.config.requests_per_second,
        )
        self.last_update = now
        self.tokens_gauge.labels(endpoint=self.endpoint).set(self.tokens)

    def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time to wait in seconds before proceeding
        """
        self._update_tokens()

        if self.tokens < tokens:
            # Calculate wait time needed for enough tokens
            wait_time = (tokens - self.tokens) / self.config.requests_per_second
            self.throttled_counter.labels(endpoint=self.endpoint).inc()
            self.wait_time_histogram.labels(endpoint=self.endpoint).observe(wait_time)
            self.logger.debug(
                "rate_limit_throttled",
                endpoint=self.endpoint,
                wait_time=wait_time,
                tokens=self.tokens,
                requested=tokens,
            )
            return wait_time

        self.tokens -= tokens
        self.tokens_gauge.labels(endpoint=self.endpoint).set(self.tokens)
        return 0.0


class EndpointRateLimiter:
    """Rate limiter that manages per-endpoint token buckets."""

    def __init__(self, default_config: RateLimitConfig):
        """Initialize the endpoint rate limiter.

        Args:
            default_config: Default rate limit configuration for new endpoints
        """
        self.default_config = default_config
        self.limiters: Dict[str, TokenBucketRateLimiter] = {}
        self.logger = structlog.get_logger(__name__)

    def get_limiter(self, endpoint: str) -> TokenBucketRateLimiter:
        """Get or create a rate limiter for an endpoint.

        Args:
            endpoint: Endpoint identifier

        Returns:
            Rate limiter for the endpoint
        """
        if endpoint not in self.limiters:
            self.limiters[endpoint] = TokenBucketRateLimiter(
                config=self.default_config,
                endpoint=endpoint,
            )
            self.logger.info(
                "created_endpoint_rate_limiter",
                endpoint=endpoint,
                rate=self.default_config.requests_per_second,
            )
        return self.limiters[endpoint]

    def acquire(self, endpoint: str, tokens: int = 1) -> float:
        """Acquire tokens for an endpoint.

        Args:
            endpoint: Endpoint identifier
            tokens: Number of tokens to acquire

        Returns:
            Time to wait in seconds before proceeding
        """
        return self.get_limiter(endpoint).acquire(tokens)
