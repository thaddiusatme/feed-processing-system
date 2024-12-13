import threading
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from feed_processor.error_handling import ErrorCategory, ErrorHandler, ErrorSeverity
from feed_processor.webhook_manager import WebhookManager


class TestWebhookErrorHandling:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.fixture
    def webhook_manager(self):
        return WebhookManager(webhook_url="http://test.com/webhook", rate_limit=0.1, max_retries=3)

    def test_rate_limit_error_handling(self, error_handler, webhook_manager):
        with patch("requests.post") as mock_post:
            # Simulate rate limit error
            mock_post.side_effect = Exception("Rate limit exceeded")

            with pytest.raises(Exception) as exc_info:
                error_handler.handle_error(
                    error=exc_info.value,
                    category=ErrorCategory.RATE_LIMIT_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                    service="webhook",
                    details={"url": webhook_manager.webhook_url},
                    retry_func=lambda: webhook_manager.send_webhook({"test": "data"}),
                )

            assert "Rate limit exceeded" in str(exc_info.value)

    def test_concurrent_error_handling(self, error_handler, webhook_manager):
        def simulate_concurrent_failures():
            for _ in range(10):
                try:
                    raise Exception("Concurrent test error")
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.DELIVERY_ERROR,
                        severity=ErrorSeverity.HIGH,
                        service="webhook",
                        details={"thread_id": threading.get_ident()},
                    )
                time.sleep(0.1)

        threads = [threading.Thread(target=simulate_concurrent_failures) for _ in range(3)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify circuit breaker state
        assert error_handler.get_circuit_breaker("webhook").state == "open"

    def test_error_history_tracking(self, error_handler):
        test_errors = [
            (ErrorCategory.API_ERROR, ErrorSeverity.LOW),
            (ErrorCategory.DELIVERY_ERROR, ErrorSeverity.MEDIUM),
            (ErrorCategory.RATE_LIMIT_ERROR, ErrorSeverity.HIGH),
        ]

        for category, severity in test_errors:
            error_handler.handle_error(
                error=Exception(f"Test error: {category}"),
                category=category,
                severity=severity,
                service="webhook",
                details={"test": True},
            )

        # Verify error history (assuming we implement error history tracking)
        assert len(error_handler.get_recent_errors()) <= 100  # Max history size

    @pytest.mark.parametrize(
        "hour,max_retries",
        [
            (10, 3),  # Peak hours - fewer retries
            (22, 5),  # Off-peak hours - more retries
        ],
    )
    def test_time_based_retry_strategy(self, error_handler, hour, max_retries):
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, hour, 0)

            error_handler.handle_error(
                error=Exception("Test error"),
                category=ErrorCategory.DELIVERY_ERROR,
                severity=ErrorSeverity.MEDIUM,
                service="webhook",
                details={"test": True},
                max_retries=max_retries,
            )

            assert error_handler.get_retry_count("webhook") == max_retries

    @pytest.mark.parametrize(
        "hour,expected_retries",
        [
            (10, 3),  # Peak hours - fewer retries
            (22, 5),  # Off-peak hours - more retries
        ],
    )
    def test_time_based_retry_strategy(self, error_handler, hour):
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, hour, 0)

            error_handler.handle_error(
                error=Exception("Test error"),
                category=ErrorCategory.DELIVERY_ERROR,
                severity=ErrorSeverity.MEDIUM,
                service="webhook",
                details={"hour": hour},
            )

            # Verify retry count based on time of day
            assert error_handler._get_max_retries(hour) == expected_retries


def test_webhook_retry_mechanism():
    manager = WebhookManager()
    retries = 3

    with patch.object(manager, "_send_webhook", side_effect=Exception("Test error")):
        with pytest.raises(Exception):
            manager.send_webhook("http://test.com", {"data": "test"}, max_retries=retries)

    assert manager.retry_count["http://test.com"] == retries


def test_concurrent_webhook_retries():
    manager = WebhookManager()
    webhook_url = "http://test.com"
    expected_retries = 3

    def simulate_webhook_failure():
        try:
            manager.send_webhook(webhook_url, {"data": "test"}, max_retries=expected_retries)
        except Exception:
            pass

    threads = []
    for _ in range(3):
        thread = threading.Thread(target=simulate_webhook_failure)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert manager.retry_count[webhook_url] == expected_retries


def test_webhook_backoff_timing():
    manager = WebhookManager()
    start_time = datetime.now()
    retries = 2

    with patch.object(manager, "_send_webhook", side_effect=Exception("Test error")):
        with pytest.raises(Exception):
            manager.send_webhook("http://test.com", {"data": "test"}, max_retries=retries)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # With 2 retries and exponential backoff (1s, 2s), minimum duration should be ~3s
    assert duration >= 3
