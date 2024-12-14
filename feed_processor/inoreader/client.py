"""
Inoreader API client implementation with production-ready features.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
import structlog
from pydantic import BaseModel, Field

from feed_processor.core.errors import APIError, NetworkError, RateLimitError
from feed_processor.metrics.prometheus import metrics
from feed_processor.storage.models import ContentItem, ContentStatus, ContentType

logger = structlog.get_logger(__name__)


class InoreaderConfig(BaseModel):
    """Configuration for Inoreader client."""

    api_token: str = Field(..., description="API token for authentication")
    base_url: str = Field(
        default="https://www.inoreader.com/reader/api/0", description="Base URL for Inoreader API"
    )
    rate_limit_delay: float = Field(
        default=0.2, description="Minimum delay between requests in seconds"
    )
    max_retries: int = Field(
        default=3, description="Maximum number of retry attempts for failed requests"
    )
    feed_tag_filter: str = Field(default="user/-/label/tech", description="Tag to filter feeds by")


class InoreaderClient:
    """Production-ready client for interacting with the Inoreader API."""

    def __init__(self, config: InoreaderConfig):
        """Initialize the Inoreader API client.

        Args:
            config: Configuration for the client
        """
        self.config = config
        self.last_request_time = 0

        # Register metrics
        metrics.register_counter(
            "inoreader_requests_total",
            "Total number of requests made to Inoreader API",
            ["operation", "status"],
        )
        metrics.register_histogram(
            "inoreader_request_duration_seconds",
            "Duration of Inoreader API requests",
            ["operation"],
        )
        metrics.register_counter(
            "inoreader_items_processed", "Number of items processed from Inoreader", ["status"]
        )

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.config.rate_limit_delay:
            delay = self.config.rate_limit_delay - time_since_last
            time.sleep(delay)
        self.last_request_time = time.time()

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """Make a rate-limited request to the Inoreader API with retries.

        Args:
            endpoint: API endpoint to call
            method: HTTP method to use
            params: Query parameters for the request
            retry_count: Current retry attempt number

        Returns:
            API response data

        Raises:
            APIError: If the API returns an error
            NetworkError: If there's a network connectivity issue
            RateLimitError: If rate limit is exceeded
        """
        self._wait_for_rate_limit()
        url = urljoin(self.config.base_url, endpoint)
        headers = {"Authorization": f"Bearer {self.config.api_token}"}

        start_time = time.time()
        operation = endpoint.split("/")[-1]

        try:
            response = requests.request(method, url, headers=headers, params=params, timeout=10)

            metrics.observe_histogram(
                "inoreader_request_duration_seconds",
                time.time() - start_time,
                {"operation": operation},
            )

            if response.status_code == 429:  # Rate limit exceeded
                metrics.increment_counter(
                    "inoreader_requests_total", {"operation": operation, "status": "rate_limited"}
                )
                if retry_count < self.config.max_retries:
                    time.sleep(2**retry_count)  # Exponential backoff
                    return self._make_request(endpoint, method, params, retry_count + 1)
                raise RateLimitError("Rate limit exceeded")

            if response.status_code == 401:
                metrics.increment_counter(
                    "inoreader_requests_total", {"operation": operation, "status": "unauthorized"}
                )
                raise APIError("Invalid API token")

            if response.status_code != 200:
                metrics.increment_counter(
                    "inoreader_requests_total", {"operation": operation, "status": "error"}
                )
                raise APIError(f"API error: {response.text}")

            metrics.increment_counter(
                "inoreader_requests_total", {"operation": operation, "status": "success"}
            )

            return response.json()

        except requests.exceptions.Timeout:
            metrics.increment_counter(
                "inoreader_requests_total", {"operation": operation, "status": "timeout"}
            )
            if retry_count < self.config.max_retries:
                return self._make_request(endpoint, method, params, retry_count + 1)
            raise NetworkError("Request timed out")

        except requests.exceptions.RequestException as e:
            metrics.increment_counter(
                "inoreader_requests_total", {"operation": operation, "status": "network_error"}
            )
            raise NetworkError(f"Network error: {str(e)}")

    async def get_stream_contents(self, continuation: Optional[str] = None) -> List[ContentItem]:
        """Get contents from the configured feed stream.

        Args:
            continuation: Token for pagination

        Returns:
            List of processed content items

        Raises:
            APIError: If the API returns an error
        """
        params = {
            "n": 50,  # Number of items per request
            "xt": "user/-/state/com.google/read",  # Exclude read items
        }

        if continuation:
            params["c"] = continuation

        response = self._make_request(
            f"stream/contents/{self.config.feed_tag_filter}", params=params
        )

        items = []
        for item in response.get("items", []):
            try:
                # Detect content type
                content_type = ContentType.BLOG  # Default
                if any(
                    vid_domain in item["canonical"][0]["href"]
                    for vid_domain in ["youtube.com", "vimeo.com"]
                ):
                    content_type = ContentType.VIDEO
                elif any(
                    social_domain in item["canonical"][0]["href"]
                    for social_domain in ["twitter.com", "linkedin.com"]
                ):
                    content_type = ContentType.SOCIAL

                content_item = ContentItem(
                    title=item["title"],
                    content=item.get("summary", {}).get("content", "")[:2000],
                    url=item["canonical"][0]["href"],
                    content_type=content_type,
                    published_at=datetime.fromtimestamp(item["published"], tz=timezone.utc),
                    source_id=item["id"],
                    status=ContentStatus.PENDING,
                )

                items.append(content_item)
                metrics.increment_counter("inoreader_items_processed", {"status": "success"})

            except (KeyError, IndexError) as e:
                logger.error("Error processing item", error=str(e), item_id=item.get("id"))
                metrics.increment_counter("inoreader_items_processed", {"status": "error"})

        return items
