"""Unit tests for the Inoreader API client."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from feed_processor.core.clients.inoreader import InoreaderClient
from feed_processor.core.errors import APIError


@pytest.fixture
def client():
    """Create a test instance of InoreaderClient."""
    return InoreaderClient(
        api_token="test-token",
        base_url="https://test.inoreader.com/reader/api/0",
        rate_limit_delay=0.01,  # Small delay for testing
        max_retries=2,
    )


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    mock = Mock()
    mock.status_code = 200
    mock.json.return_value = {
        "items": [
            {
                "id": "test-id",
                "title": "Test Item",
                "published": int(datetime.now().timestamp()),
                "origin": {"streamId": "feed/test"},
                "categories": [{"label": "test-category"}],
            }
        ],
        "continuation": "test-token",
    }
    return mock


def test_client_initialization():
    """Test client initialization with parameters."""
    client = InoreaderClient(
        api_token="test-token", base_url="https://custom.url", rate_limit_delay=0.5, max_retries=3
    )
    assert client.api_token == "test-token"
    assert client.base_url == "https://custom.url"
    assert client.rate_limit_delay == 0.5
    assert client.max_retries == 3


@patch("requests.request")
def test_get_unread_items_success(mock_request, client, mock_response):
    """Test successful retrieval of unread items."""
    mock_request.return_value = mock_response

    result = client.get_unread_items(count=10)

    assert "items" in result
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "test-id"
    assert "continuation" in result

    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert "count=10" in kwargs["url"]


@patch("requests.request")
def test_get_unread_items_with_continuation(mock_request, client, mock_response):
    """Test unread items retrieval with continuation token."""
    mock_request.return_value = mock_response

    result = client.get_unread_items(count=10, continuation="prev-token")

    assert "continuation" in result
    assert result["continuation"] == "test-token"

    args, kwargs = mock_request.call_args
    assert "continuation=prev-token" in kwargs["url"]


@patch("requests.request")
def test_rate_limit_error(mock_request, client):
    """Test handling of rate limit errors."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"error": "Rate limit exceeded"}
    mock_request.return_value = mock_response

    with pytest.raises(APIError) as exc:
        client.get_unread_items()
    assert "Rate limit exceeded" in str(exc.value)


@patch("requests.request")
def test_authentication_error(mock_request, client):
    """Test handling of authentication errors."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "Invalid token"}
    mock_request.return_value = mock_response

    with pytest.raises(APIError) as exc:
        client.get_unread_items()
    assert "Authentication failed" in str(exc.value)


@patch("requests.request")
def test_network_error(mock_request, client):
    """Test handling of network errors."""
    mock_request.side_effect = requests.exceptions.RequestException("Network error")

    with pytest.raises(APIError) as exc:
        client.get_unread_items()
    assert "Network error" in str(exc.value)


@patch("requests.request")
def test_mark_as_read_success(mock_request, client, mock_response):
    """Test successful marking of items as read."""
    mock_request.return_value = Mock(status_code=200)

    result = client.mark_as_read(["test-id-1", "test-id-2"])
    assert result is True

    args, kwargs = mock_request.call_args
    assert kwargs["method"] == "POST"
    assert "mark-as-read" in kwargs["url"]
    assert "test-id-1" in kwargs["data"]["items"]
    assert "test-id-2" in kwargs["data"]["items"]


@patch("requests.request")
def test_get_feed_metadata_success(mock_request, client):
    """Test successful retrieval of feed metadata."""
    mock_response = Mock(status_code=200)
    mock_response.json.return_value = {
        "title": "Test Feed",
        "subscribers": 100,
        "updated": int(datetime.now().timestamp()),
    }
    mock_request.return_value = mock_response

    result = client.get_feed_metadata("feed/test")
    assert result["title"] == "Test Feed"
    assert result["subscribers"] == 100


@patch("time.sleep")
@patch("time.time")
def test_rate_limiting(mock_time, mock_sleep, client):
    """Test that rate limiting delays are enforced."""
    mock_time.side_effect = [0, 0.005, 0.01]  # Simulate time progression

    client.wait_for_rate_limit()
    client.wait_for_rate_limit()

    assert mock_sleep.called
    assert mock_sleep.call_args[0][0] >= 0


@patch("requests.request")
def test_empty_mark_as_read(mock_request, client):
    """Test mark_as_read with empty list doesn't make request."""
    result = client.mark_as_read([])
    assert result is True
    mock_request.assert_not_called()


@patch("requests.request")
def test_retry_mechanism(mock_request, client):
    """Test retry mechanism for failed requests."""
    mock_response_error = Mock(status_code=500)
    mock_response_success = Mock(status_code=200, json=Mock(return_value={"items": []}))
    mock_request.side_effect = [mock_response_error, mock_response_success]

    result = client.get_unread_items()
    assert result == {"items": []}
    assert mock_request.call_count == 2


@patch("requests.request")
def test_malformed_response(mock_request, client):
    """Test handling of malformed API responses."""
    mock_response = Mock(status_code=200)
    mock_response.json.return_value = {"invalid": "response"}
    mock_request.return_value = mock_response

    with pytest.raises(APIError) as exc:
        client.get_unread_items()
    assert "Invalid response format" in str(exc.value)
