from unittest.mock import patch

import pytest

from feed_processor.webhook.manager import WebhookManager


@pytest.fixture
def mock_logger():
    """Create a mock logger that supports method chaining"""
    logger = patch("structlog.get_logger").start()
    logger.return_value.debug = patch("structlog.get_logger").start()
    logger.return_value.info = patch("structlog.get_logger").start()
    logger.return_value.warning = patch("structlog.get_logger").start()
    logger.return_value.error = patch("structlog.get_logger").start()
    logger.return_value.bind = patch("structlog.get_logger").start()
    return logger


@pytest.fixture
def webhook_manager(mock_logger):
    manager = WebhookManager(webhook_url="http://test.webhook", rate_limit=0.2, max_retries=3)
    return manager


@pytest.fixture
def valid_payload():
    return {
        "title": "Test Article",
        "contentType": ["BLOG"],
        "brief": "Test summary",
        "sourceMetadata": {"feedId": "test123"},
    }


class TestWebhookManagerLogging:
    def test_initialization_logging(self, webhook_manager):
        webhook_manager.logger.info.assert_called_with("webhook_manager_initialized")

    def test_rate_limit_logging(self, webhook_manager, valid_payload):
        with patch("time.time", side_effect=[0, 0, 0.2]):  # Initial, elapsed check, final
            webhook_manager._wait_for_rate_limit()
            webhook_manager.logger.debug.assert_called_with(
                "rate_limit_delay", sleep_time=0.2, elapsed=0
            )

    def test_validation_success_logging(self, webhook_manager, valid_payload):
        webhook_manager._validate_payload(valid_payload)
        webhook_manager.logger.debug.assert_called_with(
            "payload_validation_success", payload=valid_payload
        )

    def test_validation_failure_logging(self, webhook_manager):
        invalid_payload = {"title": "Test"}  # Missing required fields

        with pytest.raises(ValueError):
            webhook_manager._validate_payload(invalid_payload)

        # Sort missing fields to ensure consistent order
        missing_fields = ["brief", "contentType"]  # Already sorted
        webhook_manager.logger.warning.assert_called_with(
            "payload_validation_failed",
            error="missing_fields",
            missing_fields=missing_fields,
            payload=invalid_payload,
        )

    def test_request_success_logging(self, webhook_manager, valid_payload):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = "OK"

            webhook_manager.send_webhook(valid_payload)

            # Check all debug logs in sequence
            assert (
                webhook_manager.logger.debug.call_args_list[0][0][0] == "payload_validation_success"
            )
            assert webhook_manager.logger.debug.call_args_list[1][0][0] == "sending_webhook_request"
            assert webhook_manager.logger.info.call_args_list[-1][0][0] == "webhook_request_success"

    def test_request_failure_logging(self, webhook_manager, valid_payload):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"

            webhook_manager.send_webhook(valid_payload)

            webhook_manager.logger.warning.assert_any_call(
                "webhook_request_failed_retrying",
                status_code=500,
                retry_attempt=1,
                error="Internal Server Error",
            )

    def test_max_retries_logging(self, webhook_manager, valid_payload):
        with patch("requests.post") as mock_post, patch("time.time", return_value=1734080222):
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"

            response = webhook_manager.send_webhook(valid_payload)

            webhook_manager.logger.error.assert_called_with(
                "webhook_request_failed_max_retries",
                status_code=500,
                error="Internal Server Error",
                error_id=response.error_id,
            )

    def test_bulk_send_logging(self, webhook_manager, valid_payload):
        payloads = [valid_payload.copy() for _ in range(3)]

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            webhook_manager.bulk_send(payloads)

            webhook_manager.logger.info.assert_any_call("starting_bulk_send", payload_count=3)

            webhook_manager.logger.info.assert_any_call(
                "bulk_send_completed", total_items=3, success_count=3, error_count=0
            )

    def test_rate_limit_hit_logging(self, webhook_manager, valid_payload):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 429
            mock_post.return_value.text = "Rate limit exceeded"

            webhook_manager.send_webhook(valid_payload)

            webhook_manager.logger.warning.assert_any_call(
                "rate_limit_hit_adding_delay",
                delay=0.4,
                status_code=429,
                error="Rate limit exceeded",
            )

    def test_error_id_consistency(self, webhook_manager, valid_payload):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.text = "Bad Request"

            response = webhook_manager.send_webhook(valid_payload)

            # Verify error ID format
            assert response.error_id.startswith("err_")
            assert response.error_id.split("_")[2] == "400"  # Status code in error ID


def test_webhook_logging_success():
    manager = WebhookManager()
    webhook_url = "http://test.com"
    payload = {"data": "test"}

    with patch.object(manager, "_send_webhook") as mock_send:
        mock_send.return_value = {"status": "success"}
        response = manager.send_webhook(webhook_url, payload)

    assert response["status"] == "success"
    assert webhook_url not in manager.retry_count


def test_webhook_logging_failure():
    manager = WebhookManager()
    webhook_url = "http://test.com"
    payload = {"data": "test"}

    with patch.object(manager, "_send_webhook", side_effect=Exception("Test error")):
        with pytest.raises(Exception):
            manager.send_webhook(webhook_url, payload, max_retries=2)

    assert webhook_url in manager.retry_count
    assert manager.retry_count[webhook_url] == 2


def test_webhook_retry_logging():
    manager = WebhookManager()
    webhook_url = "http://test.com"
    payload = {"data": "test"}

    with patch.object(manager, "_send_webhook") as mock_send:
        mock_send.side_effect = [
            Exception("First attempt"),
            Exception("Second attempt"),
            {"status": "success"},
        ]

        response = manager.send_webhook(webhook_url, payload, max_retries=3)

    assert response["status"] == "success"
    assert webhook_url in manager.retry_count
    assert manager.retry_count[webhook_url] == 2  # Two failures before success
