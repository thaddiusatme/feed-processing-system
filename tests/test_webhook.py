import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from feed_processor.webhook import WebhookConfig, WebhookError, WebhookManager, WebhookResponse


@pytest.fixture
def webhook_config():
    return WebhookConfig(
        endpoint="https://example.com/webhook",
        auth_token="test-token",
        max_retries=3,
        retry_delay=1,
        timeout=5,
        batch_size=10,
    )


@pytest.fixture
def webhook_manager(webhook_config):
    return WebhookManager(webhook_config)


@pytest.fixture
def sample_feed():
    return {
        "type": "rss",
        "title": "Test Feed",
        "items": [
            {
                "id": "1",
                "title": "Test Item",
                "content": "Test Content",
                "published": datetime.now().isoformat(),
            }
        ],
    }


def test_webhook_config_validation():
    with pytest.raises(ValueError):
        WebhookConfig(
            endpoint="",  # Empty endpoint should raise ValueError
            auth_token="test",
            max_retries=3,
            retry_delay=1,
            timeout=5,
            batch_size=10,
        )


def test_webhook_manager_initialization(webhook_config):
    manager = WebhookManager(webhook_config)
    assert manager.config == webhook_config
    assert manager.session is not None


@patch("requests.Session.post")
def test_send_webhook_success(mock_post, webhook_manager, sample_feed):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_post.return_value = mock_response

    response = webhook_manager.send(sample_feed)

    assert isinstance(response, WebhookResponse)
    assert response.success
    assert response.status_code == 200
    mock_post.assert_called_once()


@patch("requests.Session.post")
def test_send_webhook_failure(mock_post, webhook_manager, sample_feed):
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response

    with pytest.raises(WebhookError) as exc_info:
        webhook_manager.send(sample_feed)

    assert "Failed to send webhook" in str(exc_info.value)
    assert mock_post.call_count == webhook_manager.config.max_retries


@patch("requests.Session.post")
def test_send_webhook_retry_success(mock_post, webhook_manager, sample_feed):
    # First attempt fails, second succeeds
    mock_fail = Mock()
    mock_fail.status_code = 500
    mock_fail.text = "Internal Server Error"

    mock_success = Mock()
    mock_success.status_code = 200
    mock_success.json.return_value = {"status": "success"}

    mock_post.side_effect = [mock_fail, mock_success]

    response = webhook_manager.send(sample_feed)

    assert isinstance(response, WebhookResponse)
    assert response.success
    assert response.status_code == 200
    assert mock_post.call_count == 2


@patch("requests.Session.post")
def test_send_failure_with_retry(mock_post, webhook_manager, sample_feed):
    # First two calls fail, third succeeds
    mock_post.side_effect = [
        Mock(status_code=500),
        Mock(status_code=500),
        Mock(status_code=200, json=lambda: {"status": "success"}),
    ]

    response = webhook_manager.send(sample_feed)

    assert isinstance(response, WebhookResponse)
    assert response.success
    assert response.status_code == 200
    assert response.retry_count == 2
    assert mock_post.call_count == 3


@patch("requests.Session.post")
def test_send_failure_max_retries(mock_post, webhook_manager, sample_feed):
    mock_post.return_value.status_code = 500

    response = webhook_manager.send(sample_feed)

    assert not isinstance(response, WebhookResponse)
    assert not response.success
    assert response.status_code == 500
    assert response.retry_count == webhook_manager.config.max_retries
    assert mock_post.call_count == webhook_manager.config.max_retries + 1


@patch("requests.Session.post")
def test_batch_send(mock_post, webhook_manager, sample_feed):
    feeds = [sample_feed.copy() for _ in range(5)]

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "success"}

    responses = webhook_manager.batch_send(feeds)

    assert len(responses) == 1  # One batch
    assert all(r.success for r in responses)
    mock_post.assert_called_once()


@patch("requests.Session.post")
def test_rate_limiting(mock_post, webhook_manager, sample_feed):
    mock_post.return_value.status_code = 429  # Too Many Requests
    mock_post.return_value.headers = {"Retry-After": "2"}

    response = webhook_manager.send(sample_feed)

    assert not response.success
    assert response.status_code == 429
    assert response.rate_limited


@patch("requests.Session.post")
def test_authentication_error(mock_post, webhook_manager, sample_feed):
    mock_post.return_value.status_code = 401

    response = webhook_manager.send(sample_feed)

    assert not response.success
    assert response.status_code == 401
    assert "authentication" in response.error_message.lower()


def test_payload_validation(webhook_manager):
    # Test invalid payload
    invalid_feed = {"type": "unknown"}
    with pytest.raises(WebhookError):
        webhook_manager.send(invalid_feed)
