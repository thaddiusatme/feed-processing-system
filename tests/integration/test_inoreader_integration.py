import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from feed_processor.error_handling import (ErrorCategory, ErrorHandler,
                                           ErrorSeverity)


class TestInoreaderIntegration:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.fixture
    def inoreader_token(self):
        token = os.getenv("INOREADER_TOKEN")
        if not token:
            pytest.skip("INOREADER_TOKEN environment variable not set")
        return token

    def test_authentication_error_handling(self, error_handler):
        """Test handling of authentication errors with actual API"""
        with patch.dict(os.environ, {"INOREADER_TOKEN": "invalid_token"}):
            with pytest.raises(Exception) as exc_info:
                self._make_api_call(error_handler)

            assert "authentication" in str(exc_info.value).lower()
            assert (
                error_handler.get_error_metrics()["errors_by_category"].get(
                    ErrorCategory.API_ERROR.value, 0
                )
                > 0
            )

    def test_rate_limit_recovery(self, error_handler, inoreader_token):
        """Test recovery from rate limit errors"""
        # Make rapid requests to trigger rate limit
        for _ in range(10):
            try:
                self._make_api_call(error_handler)
            except Exception:
                continue
            time.sleep(0.1)

        # Verify rate limit handling
        metrics = error_handler.get_error_metrics()
        rate_limit_errors = metrics["errors_by_category"].get(
            ErrorCategory.RATE_LIMIT_ERROR.value, 0
        )
        assert rate_limit_errors > 0

        # Wait for rate limit reset
        time.sleep(5)

        # Verify recovery
        try:
            self._make_api_call(error_handler)
            assert True  # Request should succeed
        except Exception as e:
            assert False, f"Failed to recover from rate limit: {e}"

    def test_error_recovery_flow(self, error_handler, inoreader_token):
        """Test full error recovery flow with actual API"""
        # Step 1: Force circuit breaker open
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Simulated API error")

            for _ in range(5):
                try:
                    self._make_api_call(error_handler)
                except Exception:
                    continue

        cb = error_handler._get_circuit_breaker("inoreader")
        assert cb.state == "open"

        # Step 2: Wait for reset timeout
        time.sleep(cb.reset_timeout)

        # Step 3: Verify half-open state
        assert cb.can_execute()
        assert cb.state == "half-open"

        # Step 4: Make successful request
        try:
            self._make_api_call(error_handler)
            assert cb.state == "closed"
        except Exception as e:
            pytest.fail(f"Failed to recover: {e}")

    def test_malformed_response_handling(self, error_handler, inoreader_token):
        """Test handling of malformed API responses"""
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.side_effect = ValueError("Invalid JSON")

            try:
                self._make_api_call(error_handler)
            except Exception as e:
                assert "Invalid JSON" in str(e)

                # Verify error was logged correctly
                last_error = list(error_handler.error_history)[-1]
                assert last_error.category == ErrorCategory.API_ERROR
                assert "response" in last_error.details

    def test_timeout_handling(self, error_handler, inoreader_token):
        """Test handling of API timeouts"""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = TimeoutError("Request timed out")

            start_time = time.time()
            try:
                self._make_api_call(error_handler)
            except Exception:
                pass

            duration = time.time() - start_time

            # Verify retry behavior
            assert duration >= 1.0  # Should have attempted retries

            metrics = error_handler.get_error_metrics()
            assert metrics["errors_by_category"].get(ErrorCategory.API_ERROR.value, 0) > 0

    @staticmethod
    def _make_api_call(error_handler: ErrorHandler) -> None:
        """Helper to make API call with error handling"""
        import requests

        try:
            response = requests.get(
                "https://www.inoreader.com/reader/api/0/user-info",
                headers={"Authorization": f"Bearer {os.getenv('INOREADER_TOKEN')}"},
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_handler.handle_error(
                error=e,
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service="inoreader",
                details={"endpoint": "/user-info", "timestamp": datetime.utcnow().isoformat()},
            )
            raise
