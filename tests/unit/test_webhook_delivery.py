"""Unit tests for the webhook delivery system."""

import pytest
import requests
from unittest.mock import Mock, patch

from feed_processor.webhook.delivery import WebhookDeliverySystem


@pytest.fixture
def delivery_system():
    """Create a test instance of WebhookDeliverySystem."""
    return WebhookDeliverySystem(
        webhook_url="https://test.webhook.com/endpoint",
        auth_token="test-token",
        rate_limit=0.01,  # Small delay for testing
        max_retries=2,
        retry_delay=0.01,
        batch_size=5,
    )


@pytest.fixture
def test_items():
    """Create test items for delivery."""
    return [
        {"id": "1", "title": "Test 1"},
        {"id": "2", "title": "Test 2"},
    ]


def test_system_initialization():
    """Test webhook delivery system initialization."""
    system = WebhookDeliverySystem(
        webhook_url="https://test.url",
        auth_token="secret",
        rate_limit=0.5,
        max_retries=3,
        batch_size=10,
    )
    assert system.webhook_url == "https://test.url"
    assert system.auth_token == "secret"
    assert system.rate_limit == 0.5
    assert system.max_retries == 3
    assert system.batch_size == 10


@patch("requests.post")
def test_successful_delivery(mock_post, delivery_system, test_items):
    """Test successful webhook delivery."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    success = delivery_system.deliver_batch(test_items, "test-batch")

    assert success is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args

    assert kwargs["url"] == "https://test.webhook.com/endpoint"
    assert kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert len(kwargs["json"]["items"]) == 2
    assert kwargs["json"]["batch_id"] == "test-batch"


@patch("requests.post")
def test_rate_limit_retry(mock_post, delivery_system, test_items):
    """Test retry behavior when rate limited."""
    responses = [
        Mock(status_code=429),  # First attempt - rate limited
        Mock(status_code=200),  # Second attempt - success
    ]
    mock_post.side_effect = responses

    with patch("time.sleep") as mock_sleep:
        success = delivery_system.deliver_batch(test_items)

        assert success is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called()  # Should sleep between attempts


@patch("requests.post")
def test_max_retries_exceeded(mock_post, delivery_system, test_items):
    """Test behavior when max retries are exceeded."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_post.side_effect = requests.exceptions.RequestException("Server error")

    with patch("time.sleep"):
        success = delivery_system.deliver_batch(test_items)

        assert success is False
        assert mock_post.call_count == delivery_system.max_retries + 1


def test_batch_size_limit(delivery_system):
    """Test enforcement of maximum batch size."""
    oversized_batch = [{"id": str(i)} for i in range(10)]  # More than batch_size

    with patch("requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200)
        delivery_system.deliver_batch(oversized_batch)

        args, kwargs = mock_post.call_args
        assert len(kwargs["json"]["items"]) == delivery_system.batch_size


@patch("requests.post")
def test_delivery_status_tracking(mock_post, delivery_system, test_items):
    """Test tracking of delivery status."""
    mock_post.return_value = Mock(status_code=200)

    delivery_system.deliver_batch(test_items, "test-batch")
    status = delivery_system.get_delivery_status("test-batch")

    assert status["status"] == "delivered"
    assert status["items"] == len(test_items)
    assert status["attempts"] == 1


@patch("requests.post")
def test_failed_delivery_status(mock_post, delivery_system, test_items):
    """Test status tracking for failed deliveries."""
    mock_post.side_effect = requests.exceptions.RequestException("Network error")

    with patch("time.sleep"):
        delivery_system.deliver_batch(test_items, "test-batch")
        status = delivery_system.get_delivery_status("test-batch")

        assert status["status"] == "failed"
        assert "Network error" in status["error"]
        assert status["attempts"] == delivery_system.max_retries + 1


def test_empty_batch_delivery(delivery_system):
    """Test handling of empty batch delivery."""
    success = delivery_system.deliver_batch([])
    assert success is True


def test_unknown_batch_status(delivery_system):
    """Test getting status for unknown batch."""
    status = delivery_system.get_delivery_status("nonexistent-batch")
    assert status["status"] == "unknown"
    assert status["items"] == 0


@patch("time.time")
@patch("time.sleep")
def test_rate_limiting(mock_sleep, mock_time, delivery_system):
    """Test rate limiting between deliveries."""
    # Simulate rapid requests
    mock_time.side_effect = [0, 0, 0.005, 0.005]

    delivery_system._wait_for_rate_limit()
    delivery_system._wait_for_rate_limit()

    # Should sleep for remaining time in rate limit window
    mock_sleep.assert_called_with(pytest.approx(0.01, rel=1e-3))


def test_retry_delay_calculation(delivery_system):
    """Test exponential backoff for retry delays."""
    base_delay = delivery_system.retry_delay

    assert delivery_system._get_retry_delay(0) == base_delay
    assert delivery_system._get_retry_delay(1) == base_delay * 2
    assert delivery_system._get_retry_delay(2) == base_delay * 4
    # Test maximum cap
    assert delivery_system._get_retry_delay(10) == 300  # Max 5 minutes
