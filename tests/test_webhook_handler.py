"""Tests for webhook handler."""
import json
import time
from unittest.mock import Mock, patch

import pytest
from google.oauth2.credentials import Credentials

from feed_processor.exceptions import RateLimitError, WebhookError
from feed_processor.storage import GoogleDriveStorage
from feed_processor.webhook_handler import WebhookHandler


@pytest.fixture
def mock_credentials():
    return Mock(spec=Credentials)


@pytest.fixture
def mock_drive_storage(mock_credentials):
    storage = GoogleDriveStorage(mock_credentials, "root_folder_id")
    storage.create_folder = Mock(return_value="folder_id")
    storage.write_json = Mock(return_value="file_id")
    return storage


@pytest.fixture
def webhook_handler(mock_drive_storage):
    return WebhookHandler("test_api_key", mock_drive_storage)


def test_validate_auth_success(webhook_handler):
    """Test successful API key validation."""
    assert webhook_handler.validate_auth("test_api_key") is True


def test_validate_auth_failure(webhook_handler):
    """Test failed API key validation."""
    assert webhook_handler.validate_auth("wrong_key") is False


def test_rate_limit(webhook_handler):
    """Test rate limiting."""
    # First request should succeed
    webhook_handler._check_rate_limit()

    # Second request within rate limit window should fail
    with pytest.raises(RateLimitError):
        webhook_handler._check_rate_limit()

    # Wait for rate limit window
    time.sleep(0.2)

    # Third request should succeed
    webhook_handler._check_rate_limit()


def test_process_webhook_success(webhook_handler):
    """Test successful webhook processing."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
            "author": "Test Author",
            "tags": ["test"],
        },
    }

    result = webhook_handler.process_webhook(test_data, "test_api_key")

    assert result["status"] == "success"
    assert result["idea_id"] == "test123"
    assert webhook_handler.drive_storage.create_folder.call_count == 6  # One for each subfolder
    assert webhook_handler.drive_storage.write_json.call_count == 1


def test_process_webhook_invalid_auth(webhook_handler):
    """Test webhook processing with invalid auth."""
    with pytest.raises(WebhookError, match="Invalid API key"):
        webhook_handler.process_webhook({}, "wrong_key")


def test_process_webhook_rate_limit(webhook_handler):
    """Test webhook processing with rate limiting."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    # First request should succeed
    webhook_handler.process_webhook(test_data, "test_api_key")

    # Second request should fail due to rate limit
    with pytest.raises(RateLimitError):
        webhook_handler.process_webhook(test_data, "test_api_key")
