"""Unit tests for the token bucket rate limiter."""

import time

import pytest

from feed_processor.webhook.rate_limiter import (
    EndpointRateLimiter,
    RateLimitConfig,
    TokenBucketRateLimiter,
)


class TestRateLimiter:
    """Test cases for TokenBucketRateLimiter."""

    @pytest.fixture
    def config(self):
        """Create a test rate limit configuration."""
        return RateLimitConfig(requests_per_second=5.0, burst_size=2)

    @pytest.fixture
    def rate_limiter(self, config):
        """Create a test rate limiter instance."""
        return TokenBucketRateLimiter(config=config, endpoint="test")

    def test_initial_tokens(self, rate_limiter):
        """Test that rate limiter starts with correct number of tokens."""
        assert rate_limiter.tokens == 2  # burst_size

    def test_token_replenishment(self, rate_limiter):
        """Test that tokens are replenished at the correct rate."""
        # Use all tokens
        rate_limiter.acquire(2)
        assert rate_limiter.tokens == 0

        # Wait for 0.2 seconds (should get 1 token back)
        time.sleep(0.2)
        rate_limiter._update_tokens()
        assert 0.9 <= rate_limiter.tokens <= 1.1  # Allow small float imprecision

    def test_burst_limit(self, rate_limiter):
        """Test that token count doesn't exceed burst size."""
        # Wait long enough to potentially exceed burst size
        time.sleep(1.0)
        rate_limiter._update_tokens()
        assert rate_limiter.tokens == 2  # Should be capped at burst_size

    def test_wait_time_calculation(self, rate_limiter):
        """Test wait time calculation when not enough tokens."""
        # Use all tokens
        rate_limiter.acquire(2)

        # Try to acquire 1 token immediately
        wait_time = rate_limiter.acquire(1)
        assert wait_time > 0  # Should need to wait
        assert wait_time <= 0.2  # Shouldn't wait more than 1/rate


class TestEndpointRateLimiter:
    """Test cases for EndpointRateLimiter."""

    @pytest.fixture
    def default_config(self):
        """Create a test rate limit configuration."""
        return RateLimitConfig(requests_per_second=5.0, burst_size=2)

    @pytest.fixture
    def endpoint_limiter(self, default_config):
        """Create a test endpoint rate limiter instance."""
        return EndpointRateLimiter(default_config=default_config)

    def test_endpoint_creation(self, endpoint_limiter):
        """Test that limiters are created for new endpoints."""
        endpoint = "test_endpoint"
        limiter = endpoint_limiter.get_limiter(endpoint)
        assert endpoint in endpoint_limiter.limiters
        assert limiter.endpoint == endpoint

    def test_endpoint_reuse(self, endpoint_limiter):
        """Test that same limiter is returned for same endpoint."""
        endpoint = "test_endpoint"
        limiter1 = endpoint_limiter.get_limiter(endpoint)
        limiter2 = endpoint_limiter.get_limiter(endpoint)
        assert limiter1 is limiter2

    def test_multiple_endpoints(self, endpoint_limiter):
        """Test that different endpoints get different limiters."""
        limiter1 = endpoint_limiter.get_limiter("endpoint1")
        limiter2 = endpoint_limiter.get_limiter("endpoint2")

        # Use all tokens in first limiter
        limiter1.acquire(2)

        # Second limiter should still have full tokens
        assert limiter2.tokens == 2

    def test_acquire_creates_limiter(self, endpoint_limiter):
        """Test that acquire creates limiter if needed."""
        endpoint = "test_endpoint"
        wait_time = endpoint_limiter.acquire(endpoint)
        assert endpoint in endpoint_limiter.limiters
        assert wait_time == 0  # Should get token immediately
