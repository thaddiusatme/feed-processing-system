"""Unit tests for the webhook delivery system."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from feed_processor.config.webhook_config import WebhookConfig
from feed_processor.webhook.manager import WebhookManager, WebhookResponse


@pytest.fixture
def config():
    """Create a test webhook configuration."""
    return WebhookConfig(
        retry_attempts=2,
        timeout=5,
        max_concurrent=2,
        rate_limit=0.01,  # Small delay for testing
        batch_size=5,
        auth_token="test-token",
    )


@pytest.fixture
def manager(config):
    """Create a test instance of WebhookManager."""
    return WebhookManager(webhook_url="https://test.webhook.com/endpoint", config=config)


@pytest.fixture
def test_items():
    """Create test items for delivery."""
    return [
        {
            "id": "1",
            "title": "Test 1",
            "processed_at": datetime.now().isoformat(),
            "content_type": "NEWS",
            "priority": 7,
        },
        {
            "id": "2",
            "title": "Test 2",
            "processed_at": datetime.now().isoformat(),
            "content_type": "VIDEO",
            "priority": 8,
        },
    ]


def test_manager_initialization(config):
    """Test webhook manager initialization."""
    manager = WebhookManager(webhook_url="https://test.url", config=config)
    assert manager.webhook_url == "https://test.url"
    assert manager.config == config
    assert manager.metrics is not None


@patch("requests.post")
def test_successful_delivery(mock_post, manager, test_items):
    """Test successful webhook delivery."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_post.return_value = mock_response

    response = manager.deliver_batch(test_items)
    assert response.success is True
    assert response.error is None

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["url"] == manager.webhook_url
    assert kwargs["json"]["items"] == test_items
    assert "Authorization" in kwargs["headers"]


@patch("requests.post")
def test_rate_limit_retry(mock_post, manager, test_items):
    """Test retry behavior when rate limited."""
    # First request gets rate limited
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    mock_response_429.json.return_value = {"error": "Rate limit exceeded"}

    # Second request succeeds
    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"status": "success"}

    mock_post.side_effect = [mock_response_429, mock_response_200]

    response = manager.deliver_batch(test_items)
    assert response.success is True
    assert mock_post.call_count == 2


@patch("requests.post")
def test_max_retries_exceeded(mock_post, manager, test_items):
    """Test behavior when max retries are exceeded."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": "Server error"}
    mock_post.return_value = mock_response

    response = manager.deliver_batch(test_items)
    assert response.success is False
    assert "Server error" in response.error
    assert mock_post.call_count == manager.config.retry_attempts


def test_batch_size_limit(manager):
    """Test enforcement of maximum batch size."""
    large_batch = [{"id": str(i)} for i in range(20)]
    batches = list(manager._create_batches(large_batch))

    assert all(len(batch) <= manager.config.batch_size for batch in batches)
    assert sum(len(batch) for batch in batches) == len(large_batch)


@patch("requests.post")
def test_delivery_status_tracking(mock_post, manager, test_items):
    """Test tracking of delivery status."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_post.return_value = mock_response

    # Deliver batch and check metrics
    response = manager.deliver_batch(test_items)
    assert response.success is True

    metrics = manager.get_metrics()
    assert metrics["successful_deliveries"] > 0
    assert metrics["failed_deliveries"] == 0
    assert "average_delivery_time" in metrics


@patch("requests.post")
def test_failed_delivery_status(mock_post, manager, test_items):
    """Test status tracking for failed deliveries."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": "Server error"}
    mock_post.return_value = mock_response

    response = manager.deliver_batch(test_items)
    assert response.success is False

    metrics = manager.get_metrics()
    assert metrics["failed_deliveries"] > 0
    assert "last_error" in metrics


def test_empty_batch_delivery(manager):
    """Test handling of empty batch delivery."""
    response = manager.deliver_batch([])
    assert response.success is True
    assert response.error is None


@patch("requests.post")
def test_network_error(mock_post, manager, test_items):
    """Test handling of network errors."""
    mock_post.side_effect = requests.exceptions.RequestException("Network error")

    response = manager.deliver_batch(test_items)
    assert response.success is False
    assert "Network error" in response.error


@patch("requests.post")
def test_invalid_response(mock_post, manager, test_items):
    """Test handling of invalid response format."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response

    response = manager.deliver_batch(test_items)
    assert response.success is False
    assert "Invalid response format" in response.error


@patch("time.sleep")
@patch("time.time")
def test_rate_limiting(mock_time, mock_sleep, manager):
    """Test rate limiting between deliveries."""
    mock_time.side_effect = [0, 0.005, 0.01]  # Simulate time progression

    manager.rate_limiter.wait()
    manager.rate_limiter.wait()

    assert mock_sleep.called
    assert mock_sleep.call_args[0][0] >= 0


def test_response_object():
    """Test WebhookResponse object behavior."""
    success_response = WebhookResponse(True)
    assert success_response.success is True
    assert success_response.error is None

    error_response = WebhookResponse(False, "Test error")
    assert error_response.success is False
    assert error_response.error == "Test error"


@patch("requests.post")
def test_concurrent_delivery(mock_post, manager):
    """Test concurrent delivery handling."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_post.return_value = mock_response

    # Create multiple batches
    batches = [test_items for _ in range(5)]

    # Deliver all batches
    responses = []
    for batch in batches:
        responses.append(manager.deliver_batch(batch))

    assert all(response.success for response in responses)
    assert mock_post.call_count == len(batches)
