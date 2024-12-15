"""Unit tests for the WebhookManager class."""

from unittest.mock import Mock, patch

import pytest
import requests

from feed_processor.webhook.manager import WebhookManager


@pytest.fixture(autouse=True)
def mock_metrics():
    """Mock Prometheus metrics to prevent registration conflicts."""
    with patch("feed_processor.webhook.manager.metrics") as mock_metrics:
        # Create mock counters and histograms that do nothing
        mock_counter = Mock()
        mock_counter.inc = Mock()
        mock_counter.labels = Mock(return_value=mock_counter)

        mock_histogram = Mock()
        mock_histogram.observe = Mock()

        mock_gauge = Mock()
        mock_gauge.set = Mock()

        # Set up the mock metrics module
        mock_metrics.register_counter.return_value = mock_counter
        mock_metrics.register_histogram.return_value = mock_histogram
        mock_metrics.register_gauge.return_value = mock_gauge
        yield mock_metrics


@pytest.fixture
def webhook_manager():
    """Create a WebhookManager instance for testing."""
    return WebhookManager(
        webhook_url="https://test-webhook.example.com/endpoint",
        max_retries=2,
        retry_delay=0.1,  # Shorter for testing
        batch_size=10,
    )


@pytest.fixture
def valid_payload():
    """Create a valid webhook payload for testing."""
    return {
        "title": "Test Article",
        "contentType": ["BLOG"],
        "brief": "This is a test article",
        "priority": "Medium",
        "sourceMetadata": {
            "feedId": "123",
            "originalUrl": "https://example.com/article",
            "publishDate": "2024-12-12T12:00:00Z",
        },
    }


def test_validate_payload_success(webhook_manager, valid_payload, mock_metrics):
    """Test that a valid payload passes validation."""
    assert webhook_manager._validate_payload(valid_payload) is True


def test_validate_payload_missing_fields(webhook_manager, mock_metrics):
    """Test that payload validation fails when required fields are missing."""
    invalid_payload = {
        "title": "Test",
        "contentType": ["BLOG"],
        # Missing 'brief'
    }
    assert webhook_manager._validate_payload(invalid_payload) is False


def test_validate_payload_invalid_content_type(webhook_manager, valid_payload, mock_metrics):
    """Test that payload validation fails with invalid content type."""
    invalid_payload = valid_payload.copy()
    invalid_payload["contentType"] = ["INVALID_TYPE"]
    assert webhook_manager._validate_payload(invalid_payload) is False


def test_validate_payload_title_too_long(webhook_manager, valid_payload, mock_metrics):
    """Test that payload validation fails when title exceeds maximum length."""
    invalid_payload = valid_payload.copy()
    invalid_payload["title"] = "x" * 256
    assert webhook_manager._validate_payload(invalid_payload) is False


@patch("requests.post")
def test_send_batch_success(mock_post, webhook_manager, valid_payload, mock_metrics):
    """Test successful batch sending of webhooks."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    response = webhook_manager.send_batch([valid_payload])

    assert response.success is True
    assert response.status_code == 200
    assert response.error_type is None
    mock_post.assert_called_once()


@patch("requests.post")
def test_send_batch_rate_limit(mock_post, webhook_manager, valid_payload, mock_metrics):
    """Test handling of rate limiting in webhook sending."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_post.return_value = mock_response

    response = webhook_manager.send_batch([valid_payload])

    assert response.success is False
    assert response.status_code == 429
    assert response.error_type == "rate_limited"
    assert response.error_message == "Rate limit exceeded"


@patch("requests.post")
def test_send_batch_server_error_retry(mock_post, webhook_manager, valid_payload, mock_metrics):
    """Test retry behavior on server errors."""
    error_response = Mock()
    error_response.status_code = 500
    success_response = Mock()
    success_response.status_code = 200

    mock_post.side_effect = [error_response, success_response]

    response = webhook_manager.send_batch([valid_payload])

    assert response.success is True
    assert response.status_code == 200
    assert mock_post.call_count == 2


@patch("requests.post")
def test_send_items(mock_post, webhook_manager, valid_payload, mock_metrics):
    """Test sending multiple items in batches."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Create multiple valid payloads
    items = [valid_payload.copy() for _ in range(25)]
    responses = webhook_manager.send_items(items)

    # With batch_size=10, we expect 3 batches
    assert len(responses) == 3
    assert all(r.success for r in responses)
    assert mock_post.call_count == 3


def test_batch_size_limit(webhook_manager, valid_payload, mock_metrics):
    """Test that batches don't exceed the maximum size."""
    items = [valid_payload.copy() for _ in range(15)]

    with patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        responses = webhook_manager.send_items(items)

        # With batch_size=10, we expect 2 batches
        assert len(responses) == 2
        assert mock_post.call_count == 2

        # First call should have 10 items, second should have 5
        first_call_items = mock_post.call_args_list[0][1]["json"]["items"]
        second_call_items = mock_post.call_args_list[1][1]["json"]["items"]
        assert len(first_call_items) == 10
        assert len(second_call_items) == 5


@patch("requests.post")
def test_connection_error_retry(mock_post, webhook_manager, valid_payload, mock_metrics):
    """Test retry behavior on connection errors."""
    mock_post.side_effect = [
        requests.exceptions.ConnectionError("Network error"),
        Mock(status_code=200),
    ]

    response = webhook_manager.send_batch([valid_payload])

    assert response.success is True
    assert response.status_code == 200
    assert response.error_type is None
    assert response.error_message is None
    assert mock_post.call_count == 2
