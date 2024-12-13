import pytest
import requests
from unittest.mock import Mock, patch
import time
from datetime import datetime
from feed_processor.webhook_manager import WebhookManager, WebhookResponse


@pytest.fixture
def webhook_manager():
    return WebhookManager(
        webhook_url="https://test-webhook.example.com/endpoint",
        rate_limit=0.1,  # Shorter for testing
        max_retries=2,
    )


@pytest.fixture
def valid_payload():
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


def test_validate_payload_success(webhook_manager, valid_payload):
    assert webhook_manager._validate_payload(valid_payload) is True


def test_validate_payload_missing_fields(webhook_manager):
    invalid_payload = {
        "title": "Test",
        "contentType": ["BLOG"],
        # Missing 'brief'
    }
    assert webhook_manager._validate_payload(invalid_payload) is False


def test_validate_payload_invalid_content_type(webhook_manager, valid_payload):
    invalid_payload = valid_payload.copy()
    invalid_payload["contentType"] = ["INVALID_TYPE"]
    assert webhook_manager._validate_payload(invalid_payload) is False


def test_validate_payload_title_too_long(webhook_manager, valid_payload):
    invalid_payload = valid_payload.copy()
    invalid_payload["title"] = "x" * 256
    assert webhook_manager._validate_payload(invalid_payload) is False


@patch("requests.post")
def test_send_webhook_success(mock_post, webhook_manager, valid_payload):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    response = webhook_manager.send_webhook(valid_payload)

    assert response.success is True
    assert response.status_code == 200
    assert response.error_id is None
    assert response.error_type is None


@patch("requests.post")
def test_send_webhook_rate_limit(mock_post, webhook_manager, valid_payload):
    mock_response = Mock()
    mock_response.status_code = 429
    mock_post.return_value = mock_response

    response = webhook_manager.send_webhook(valid_payload)

    assert response.success is False
    assert response.status_code == 429
    assert response.error_type == "Exception"
    assert "Rate limit exceeded" in str(response.error_id)


@patch("requests.post")
def test_send_webhook_server_error_retry(mock_post, webhook_manager, valid_payload):
    error_response = Mock()
    error_response.status_code = 500
    success_response = Mock()
    success_response.status_code = 200

    mock_post.side_effect = [error_response, success_response]

    response = webhook_manager.send_webhook(valid_payload)

    assert response.success is True
    assert response.status_code == 200
    assert mock_post.call_count == 2


@patch("requests.post")
def test_bulk_send(mock_post, webhook_manager):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    payloads = [
        {"title": f"Test Article {i}", "contentType": ["BLOG"], "brief": f"Test brief {i}"}
        for i in range(3)
    ]

    responses = webhook_manager.bulk_send(payloads)

    assert len(responses) == 3
    assert all(r.success for r in responses)
    assert all(r.status_code == 200 for r in responses)


def test_rate_limiting(webhook_manager, valid_payload):
    with patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        start_time = time.time()
        webhook_manager.bulk_send([valid_payload] * 3)
        elapsed_time = time.time() - start_time

        # With rate_limit of 0.1s, 3 requests should take at least 0.2s
        assert elapsed_time >= 0.2


@patch("requests.post")
def test_connection_error_retry(mock_post, webhook_manager, valid_payload):
    mock_post.side_effect = [requests.exceptions.ConnectionError(), Mock(status_code=200)]

    response = webhook_manager.send_webhook(valid_payload)

    assert response.success is True
    assert response.status_code == 200
    assert mock_post.call_count == 2
