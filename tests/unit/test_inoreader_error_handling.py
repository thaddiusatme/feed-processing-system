from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from feed_processor.error_handling import (CircuitBreaker, ErrorCategory,
                                           ErrorHandler, ErrorSeverity)


class TestInoreaderErrorHandling:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.fixture
    def mock_inoreader_client(self):
        return Mock()

    def test_auth_error_handling(self, error_handler, mock_inoreader_client):
        # Simulate authentication error
        mock_inoreader_client.fetch_feeds.side_effect = Exception("Invalid or expired token")

        with pytest.raises(Exception) as exc_info:
            error_handler.handle_error(
                error=exc_info.value,
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service="inoreader",
                details={"operation": "fetch_feeds"},
                retry_func=mock_inoreader_client.fetch_feeds,
            )

        # Should not retry auth errors
        assert mock_inoreader_client.fetch_feeds.call_count == 1

    def test_rate_limit_handling(self, error_handler, mock_inoreader_client):
        # Simulate rate limit error
        mock_inoreader_client.fetch_feeds.side_effect = [
            Exception("429 Too Many Requests"),
            Exception("429 Too Many Requests"),
            "Success",
        ]

        result = error_handler.handle_error(
            error=Exception("429 Too Many Requests"),
            category=ErrorCategory.RATE_LIMIT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            service="inoreader",
            details={"operation": "fetch_feeds"},
            retry_func=mock_inoreader_client.fetch_feeds,
        )

        assert result == "Success"
        assert mock_inoreader_client.fetch_feeds.call_count == 3

    def test_malformed_response_handling(self, error_handler, mock_inoreader_client):
        # Simulate malformed JSON response
        mock_inoreader_client.fetch_feeds.side_effect = Exception("Invalid JSON response")

        with pytest.raises(Exception) as exc_info:
            error_handler.handle_error(
                error=exc_info.value,
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service="inoreader",
                details={"operation": "fetch_feeds", "error_type": "MalformedResponse"},
            )

        # Should log detailed error info for debugging
        assert "Invalid JSON" in str(exc_info.value)

    def test_half_open_state_transition(self, error_handler):
        service = "inoreader"
        cb = error_handler._get_circuit_breaker(service)

        # Force circuit breaker to open
        for _ in range(5):
            cb.record_failure()
        assert cb.state == "open"

        # Simulate time passing
        with patch("time.time") as mock_time:
            mock_time.return_value = time.time() + 61  # Past reset timeout

            # Should transition to half-open
            assert cb.can_execute() is True
            assert cb.state == "half-open"

            # Simulate successful request
            cb.record_success()
            assert cb.state == "closed"

            # Simulate failure in half-open state
            cb._update_state("half-open")
            cb.record_failure()
            assert cb.state == "open"

    def test_custom_retry_strategy(self, error_handler, mock_inoreader_client):
        # Test different retry strategies based on error type
        errors = [
            (ErrorCategory.RATE_LIMIT_ERROR, 5),  # More retries for rate limits
            (ErrorCategory.API_ERROR, 3),  # Standard retries for API errors
            (ErrorCategory.SYSTEM_ERROR, 2),  # Fewer retries for system errors
        ]

        for category, expected_retries in errors:
            error_context = error_handler._create_error_context(
                error=Exception("Test error"),
                category=category,
                severity=ErrorSeverity.MEDIUM,
                details={"test": True},
            )

            assert error_context.max_retries == expected_retries

    def test_error_detail_levels(self, error_handler):
        # Test different error detail levels for different destinations
        error = Exception("Sensitive error details")
        error_context = error_handler._create_error_context(
            error=error,
            category=ErrorCategory.API_ERROR,
            severity=ErrorSeverity.HIGH,
            details={"api_key": "secret", "user_id": "12345", "public_info": "viewable"},
        )

        # System logs should have full details
        system_log = error_handler._format_system_log(error_context)
        assert "api_key" in system_log
        assert "user_id" in system_log

        # Airtable logs should have limited details
        airtable_log = error_handler._format_airtable_log(error_context)
        assert "api_key" not in airtable_log
        assert "public_info" in airtable_log
