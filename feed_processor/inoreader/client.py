"""Inoreader API client."""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import aiohttp
import structlog
from prometheus_async.aio import time as prometheus_async_time
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, HttpUrl

from feed_processor.core.errors import APIError
from feed_processor.storage.models import ContentItem, ContentType, SourceMetadata

logger = structlog.get_logger(__name__)


class InoreaderConfig(BaseModel):
    """Configuration for Inoreader client."""

    app_id: str
    api_key: str
    token: str
    base_url: HttpUrl = "https://www.inoreader.com/reader/api/0"
    max_retries: int = 3
    rate_limit: int = 50  # requests per minute


class InoreaderClient:
    """Inoreader API client."""

    def __init__(self, config: InoreaderConfig):
        """Initialize Inoreader client.

        Args:
            config: Inoreader client configuration
        """
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(config.rate_limit)
        self._rate_limit_task = None

        # Initialize metrics
        self.request_duration = Histogram(
            "inoreader_request_duration_seconds", "Duration of Inoreader API requests", ["endpoint"]
        )
        self.request_total = Counter(
            "inoreader_request_total",
            "Total number of Inoreader API requests",
            ["endpoint", "status"],
        )

    async def _init_session(self):
        """Initialize aiohttp session with proper headers."""
        if self.session is None:
            headers = {
                "Authorization": f"Bearer {self.config.token}",  # Use OAuth token
                "X-AppId": self.config.app_id,
                "X-AppKey": self.config.api_key,
                "User-Agent": "FeedProcessor/1.0",
                "Accept": "application/json",
            }
            logger.debug("Request headers", headers=headers)
            self.session = aiohttp.ClientSession(headers=headers)

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None):
        """Make a request to the Inoreader API."""
        await self._init_session()
        async with self.session.request(method, endpoint, params=params) as response:
            return response

    async def get_subscription_list(self) -> List[Dict]:
        """Get list of subscribed feeds."""
        await self._init_session()
        params = {"AppId": self.config.app_id, "AppKey": self.config.api_key}
        endpoint = f"{self.config.base_url}/subscription/list"
        async with self._rate_limiter:
            async with self.session.get(endpoint, params=params) as response:
                logger.debug("API response", status=response.status, headers=response.headers)
                text = await response.text()
                logger.debug("API response body", body=text[:500])
                if response.status == 200 and response.headers.get("content-type", "").startswith(
                    "application/json"
                ):
                    return (await response.json()).get("subscriptions", [])
                return []

    async def get_stream_contents(
        self, continuation: Optional[str] = None, count: int = 20
    ) -> List[Dict[str, Any]]:
        """Get stream contents from Inoreader.

        Args:
            continuation: Continuation token for pagination
            count: Number of items to return

        Returns:
            List of feed items
        """
        await self._init_session()

        # Add required parameters
        params = {"n": count, "xt": "user/-/state/com.google/read"}  # Exclude read items
        if continuation:
            params["c"] = continuation

        request_url = f"{self.config.base_url}/stream/contents/user/-/state/com.google/reading-list?{urlencode(params)}"

        logger.info("Making request to URL", url=request_url)

        retries = 0
        while retries < self.config.max_retries:
            try:
                async with self._rate_limiter:

                    @prometheus_async_time(self.request_duration.labels(endpoint="stream_contents"))
                    async def _make_request():
                        async with self.session.get(request_url) as response:
                            if response.status == 200:
                                self.request_total.labels(
                                    endpoint="stream_contents", status="success"
                                ).inc()
                                data = await response.json()
                                items = []
                                for raw_item in data.get("items", []):
                                    try:
                                        # Extract URL and detect content type
                                        item_url = raw_item["canonical"][0]["href"]
                                        content_type = ContentType.BLOG  # Default

                                        if any(
                                            vid_domain in item_url.lower()
                                            for vid_domain in [
                                                "youtube.com",
                                                "vimeo.com",
                                                "dailymotion.com",
                                            ]
                                        ):
                                            content_type = ContentType.VIDEO
                                        elif any(
                                            social_domain in item_url.lower()
                                            for social_domain in [
                                                "twitter.com",
                                                "linkedin.com",
                                                "facebook.com",
                                                "instagram.com",
                                            ]
                                        ):
                                            content_type = ContentType.SOCIAL

                                        # Create content item
                                        item = ContentItem(
                                            title=raw_item["title"],
                                            content_type=content_type,
                                            brief=raw_item.get("summary", {}).get("content", "")[
                                                :2000
                                            ],
                                            sourceMetadata=SourceMetadata(
                                                feedId=raw_item["id"],
                                                originalUrl=item_url,
                                                publishDate=datetime.fromtimestamp(
                                                    raw_item["published"], tz=timezone.utc
                                                ),
                                                author=raw_item.get("author"),
                                                tags=[
                                                    tag["label"] for tag in raw_item.get("tags", [])
                                                ],
                                            ),
                                        )
                                        items.append(item)
                                    except Exception as e:
                                        logger.error(
                                            "Error processing item",
                                            error=str(e),
                                            item_id=raw_item.get("id", "unknown"),
                                        )
                                return items
                            else:
                                self.request_total.labels(
                                    endpoint="stream_contents", status="error"
                                ).inc()
                                error_body = await response.text()
                                logger.error(
                                    "Error fetching stream contents",
                                    status=response.status,
                                    body=error_body,
                                )
                                if response.status == 403:
                                    raise APIError(f"Invalid API token: {error_body}")
                                return []

                    return await _make_request()

            except APIError:
                raise
            except Exception as e:
                self.request_total.labels(endpoint="stream_contents", status="error").inc()
                logger.error("Error fetching stream contents", error=str(e))

            retries += 1
            if retries < self.config.max_retries:
                await asyncio.sleep(2**retries)  # Exponential backoff

        raise Exception(f"Failed to fetch stream contents after {self.config.max_retries} retries")

    async def get_stream_contents_by_stream_id(self, stream_id: str, count: int = 20) -> List[Dict]:
        """Get items from a stream/feed.

        Args:
            stream_id: The ID of the stream to fetch. For a feed, use feed/{feed_url}
            count: Number of items to fetch (default 20, max 50)
        """
        await self._init_session()
        endpoint = f"{self.config.base_url}/stream/contents/{stream_id}"
        params = {
            "n": min(count, 50),  # Cap at 50 items per request
            "r": "o",  # Show oldest items first
        }
        async with self._rate_limiter:
            async with self.session.get(endpoint, params=params) as response:
                data = await response.json()
                return data.get("items", [])

    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
