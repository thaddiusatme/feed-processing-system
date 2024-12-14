"""
Integration tests for Inoreader client.
"""
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from feed_processor.core.errors import APIError, NetworkError, RateLimitError
from feed_processor.inoreader.client import InoreaderClient, InoreaderConfig
from feed_processor.storage.models import ContentType


@pytest.fixture
def inoreader_config():
    """Create Inoreader configuration from environment variables."""
    token = os.getenv("INOREADER_TOKEN")
    if not token:
        pytest.skip("INOREADER_TOKEN environment variable not set")

    return InoreaderConfig(
        api_token=token, rate_limit_delay=0.2, max_retries=3, feed_tag_filter="user/-/label/tech"
    )


@pytest.fixture
def inoreader_client(inoreader_config):
    """Create Inoreader client instance."""
    return InoreaderClient(inoreader_config)


@pytest.mark.asyncio
async def test_get_stream_contents(inoreader_client):
    """Test fetching and processing stream contents."""
    items = await inoreader_client.get_stream_contents()

    assert items, "Should return some items"
    for item in items:
        # Verify required fields
        assert item.title, "Item should have a title"
        assert item.content, "Item should have content"
        assert item.url, "Item should have a URL"
        assert isinstance(item.content_type, ContentType), "Should have valid content type"
        assert isinstance(item.published_at, datetime), "Should have valid publication date"
        assert item.published_at.tzinfo == timezone.utc, "Date should be UTC"
        assert item.source_id, "Should have source ID"

        # Verify field constraints
        assert len(item.title) <= 255, "Title should not exceed 255 chars"
        assert len(item.content) <= 2000, "Content should not exceed 2000 chars"


@pytest.mark.asyncio
async def test_invalid_token_handling():
    """Test handling of invalid API token."""
    config = InoreaderConfig(api_token="invalid_token", rate_limit_delay=0.2, max_retries=1)
    client = InoreaderClient(config)

    with pytest.raises(APIError) as exc_info:
        await client.get_stream_contents()
    assert "Invalid API token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rate_limit_handling(inoreader_client):
    """Test handling of rate limits."""
    # Make rapid requests to trigger rate limiting
    for _ in range(10):
        try:
            await inoreader_client.get_stream_contents()
        except RateLimitError:
            # Expected behavior
            return

    pytest.fail("Should have triggered rate limit error")


@pytest.mark.asyncio
async def test_network_error_handling(inoreader_config):
    """Test handling of network errors."""
    with patch("requests.request") as mock_request:
        mock_request.side_effect = ConnectionError("Network error")

        client = InoreaderClient(inoreader_config)
        with pytest.raises(NetworkError) as exc_info:
            await client.get_stream_contents()

        assert "Network error" in str(exc_info.value)
