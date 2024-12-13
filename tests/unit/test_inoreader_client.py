"""Unit tests for the Inoreader API client."""

import pytest
import requests
from unittest.mock import Mock, patch

from feed_processor.core.clients.inoreader import InoreaderClient
from feed_processor.core.errors import APIError


@pytest.fixture
def client():
    """Create a test instance of InoreaderClient."""
    return InoreaderClient(
        api_token="test-token",
        base_url="https://test.inoreader.com/reader/api/0",
        rate_limit_delay=0.01,  # Small delay for testing
    )


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {"items": [{"id": "test-id", "title": "Test Item"}]}
    return mock


def test_client_initialization():
    """Test client initialization with parameters."""
    client = InoreaderClient(
        api_token="test-token",
        base_url="https://custom.url",
        rate_limit_delay=0.5,
    )
    assert client.api_token == "test-token"
    assert client.base_url == "https://custom.url"
    assert client.rate_limit_delay == 0.5


@patch("requests.request")
def test_get_unread_items_success(mock_request, client, mock_response):
    """Test successful retrieval of unread items."""
    mock_request.return_value = mock_response

    result = client.get_unread_items(count=10)

    assert result == {"items": [{"id": "test-id", "title": "Test Item"}]}
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["params"] == {"n": 10}
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"


@patch("requests.request")
def test_get_unread_items_with_continuation(mock_request, client, mock_response):
    """Test unread items retrieval with continuation token."""
    mock_request.return_value = mock_response

    result = client.get_unread_items(continuation="test-token", count=5)

    assert result == {"items": [{"id": "test-id", "title": "Test Item"}]}
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["params"] == {"n": 5, "c": "test-token"}


@patch("requests.request")
def test_rate_limit_error(mock_request, client):
    """Test handling of rate limit errors."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_request.return_value = mock_response

    with pytest.raises(APIError):
        client.get_unread_items()


@patch("requests.request")
def test_authentication_error(mock_request, client):
    """Test handling of authentication errors."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_request.return_value = mock_response
    mock_request.side_effect = requests.exceptions.HTTPError(response=mock_response)

    with pytest.raises(APIError) as exc_info:
        client.get_unread_items()
    assert "Invalid Inoreader API token" in str(exc_info.value)


@patch("requests.request")
def test_network_error(mock_request, client):
    """Test handling of network errors."""
    mock_request.side_effect = requests.exceptions.ConnectionError("Network error")

    with pytest.raises(APIError) as exc_info:
        client.get_unread_items()
    assert "Failed to connect to Inoreader API" in str(exc_info.value)


@patch("requests.request")
def test_mark_as_read_success(mock_request, client, mock_response):
    """Test successful marking of items as read."""
    mock_request.return_value = mock_response

    client.mark_as_read(["item1", "item2"])

    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["params"]["i"] == ["item1", "item2"]
    assert kwargs["params"]["a"] == "user/-/state/com.google/read"
    assert kwargs["params"]["r"] == "user/-/state/com.google/unread"


@patch("requests.request")
def test_get_feed_metadata_success(mock_request, client, mock_response):
    """Test successful retrieval of feed metadata."""
    mock_request.return_value = mock_response
    feed_url = "http://example.com/feed.xml"

    result = client.get_feed_metadata(feed_url)

    assert result == {"items": [{"id": "test-id", "title": "Test Item"}]}
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["params"]["quickadd"] == feed_url


def test_rate_limiting(client):
    """Test that rate limiting delays are enforced."""
    with patch("time.sleep") as mock_sleep:
        with patch("time.time") as mock_time:
            # Simulate rapid requests
            mock_time.side_effect = [0, 0, 0.005, 0.005]  # Two pairs of start/end times

            client._wait_for_rate_limit()
            client._wait_for_rate_limit()

            # Should sleep for remaining time in rate limit window
            mock_sleep.assert_called_with(pytest.approx(0.01, rel=1e-3))


@patch("requests.request")
def test_empty_mark_as_read(mock_request, client):
    """Test mark_as_read with empty list doesn't make request."""
    client.mark_as_read([])
    mock_request.assert_not_called()
