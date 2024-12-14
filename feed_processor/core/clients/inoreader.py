"""Inoreader API client implementation."""

import time
from typing import Any, Dict, List, Optional

import requests
import structlog

from feed_processor.core.errors import APIError
from feed_processor.metrics.prometheus import metrics


class InoreaderClient:
    """Client for interacting with the Inoreader API."""

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://www.inoreader.com/reader/api/0",
        rate_limit_delay: float = 0.2,
    ):
        """Initialize the Inoreader client.

        Args:
            api_token: API token for authentication
            base_url: Base URL for Inoreader API
            rate_limit_delay: Delay between API requests in seconds
        """
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self.logger = structlog.get_logger(__name__)

        # Initialize metrics
        self.request_counter = metrics.register_counter(
            "inoreader_requests_total", "Total number of Inoreader API requests", ["status"]
        )
        self.request_latency = metrics.register_histogram(
            "inoreader_request_duration_seconds", "Duration of Inoreader API requests in seconds"
        )

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the Inoreader API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            API response data

        Raises:
            APIError: If the API request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            start_time = time.time()
            response = requests.request(method, url, headers=headers, **kwargs)
            duration = time.time() - start_time

            # Record metrics
            self.request_latency.observe(duration)
            self.request_counter.labels(status=str(response.status_code)).inc()

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.error("Inoreader API request failed", error=str(e))
            raise APIError(f"Inoreader API request failed: {str(e)}")

        finally:
            # Rate limiting
            time.sleep(self.rate_limit_delay)

    def get_unread_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get unread items from Inoreader.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of unread items
        """
        endpoint = "stream/contents/user/-/state/com.google/reading-list"
        params = {
            "n": limit,
            "xt": "user/-/state/com.google/read",  # Exclude read items
        }

        response = self._make_request("GET", endpoint, params=params)
        return response.get("items", [])

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
