"""Inoreader API client implementation."""

import time
from typing import Any, Dict, List, Optional

import requests
import structlog

from feed_processor.core.errors import APIError
from feed_processor.metrics.prometheus import MetricsCollector


class InoreaderClient:
    """Client for interacting with the Inoreader API."""

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://www.inoreader.com/reader/api/0",
        rate_limit_delay: float = 0.2,
    ):
        """Initialize the Inoreader API client.

        Args:
            api_token: API token for authentication
            base_url: Base URL for Inoreader API
            rate_limit_delay: Minimum delay between requests in seconds
        """
        self.api_token = api_token
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.metrics = MetricsCollector()
        self.logger = structlog.get_logger(__name__)

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            delay = self.rate_limit_delay - time_since_last
            self.metrics.record("rate_limit_delay", delay)
            time.sleep(self.rate_limit_delay)  # Always sleep for full delay
        self.last_request_time = time.time()

    def _make_request(
        self, endpoint: str, method: str = "GET", params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a rate-limited request to the Inoreader API.

        Args:
            endpoint: API endpoint to call
            method: HTTP method to use
            params: Optional query parameters

        Returns:
            API response data

        Raises:
            RateLimitError: If rate limit is exceeded
            NetworkError: If network request fails
            FeedProcessingError: For other API errors
        """
        self._wait_for_rate_limit()

        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            start_time = time.time()
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
            )
            self.metrics.record("api_latency", time.time() - start_time)

            if response.status_code == 429:
                self.metrics.increment("api_requests", labels={"status": "rate_limited"})
                raise APIError("Inoreader API rate limit exceeded")

            response.raise_for_status()
            self.metrics.increment("api_requests", labels={"status": "success"})

            return response.json()

        except requests.exceptions.RequestException as e:
            self.metrics.increment("api_requests", labels={"status": "failed"})
            self.logger.error(
                "inoreader_api_request_failed",
                error=str(e),
                url=url,
                status_code=getattr(e.response, "status_code", None),
            )
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code == 401:
                    raise APIError("Invalid Inoreader API token")
                elif e.response.status_code == 403:
                    raise APIError("Insufficient permissions")
            raise APIError(f"Failed to connect to Inoreader API: {e}")

    def get_unread_items(
        self, continuation: Optional[str] = None, count: int = 100
    ) -> Dict[str, Any]:
        """Fetch unread items from the reading list.

        Args:
            continuation: Token for pagination
            count: Number of items to fetch

        Returns:
            Dict containing feed items and continuation token
        """
        params = {"n": count}
        if continuation:
            params["c"] = continuation

        return self._make_request(
            "stream/contents/user/-/state/com.google/reading-list",
            params=params,
        )

    def mark_as_read(self, item_ids: List[str]) -> None:
        """Mark items as read.

        Args:
            item_ids: List of item IDs to mark as read
        """
        if not item_ids:
            return

        self._make_request(
            "edit-tag",
            method="POST",
            params={
                "i": item_ids,
                "a": "user/-/state/com.google/read",
                "r": "user/-/state/com.google/unread",
            },
        )

    def get_feed_metadata(self, feed_url: str) -> Dict[str, Any]:
        """Get metadata for a feed.

        Args:
            feed_url: URL of the feed

        Returns:
            Feed metadata
        """
        return self._make_request(
            "subscription/quickadd",
            params={"quickadd": feed_url},
        )
