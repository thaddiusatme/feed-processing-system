import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from feed_processor.error_handling import (CircuitBreaker, ErrorCategory,
                                           ErrorContext, ErrorHandler,
                                           ErrorSeverity)


class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failures == 0
        assert cb.can_execute() is True

    def test_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == "closed"
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_reset_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False

        time.sleep(0.2)  # Wait for reset timeout
        assert cb.can_execute() is True
        assert cb.state == "half-open"

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        assert cb.failures == 1

        cb.record_success()
        assert cb.failures == 0
        assert cb.state == "closed"


class TestErrorContext:
    def test_error_context_creation(self):
        context = ErrorContext(
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_id="test_error_1",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.API_ERROR,
            message="Test error",
            details={"test": "data"},
        )

        assert context.error_id == "test_error_1"
        assert context.severity == ErrorSeverity.HIGH
        assert context.category == ErrorCategory.API_ERROR
        assert context.message == "Test error"
        assert context.details == {"test": "data"}
        assert context.retry_count == 0
        assert context.max_retries == 3


class TestErrorHandler:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    def test_circuit_breaker_creation(self, error_handler):
        service = "test_service"
        cb = error_handler._get_circuit_breaker(service)
        assert service in error_handler.circuit_breakers
        assert isinstance(cb, CircuitBreaker)

        # Getting the same service should return the same circuit breaker
        cb2 = error_handler._get_circuit_breaker(service)
        assert cb is cb2

    def test_backoff_calculation(self, error_handler):
        # Test that backoff increases exponentially
        delay1 = error_handler._calculate_backoff(0)
        delay2 = error_handler._calculate_backoff(1)
        delay3 = error_handler._calculate_backoff(2)

        assert delay1 < delay2 < delay3
        assert delay3 <= 30  # Check maximum cap

    @patch("logging.Logger.error")
    def test_error_handling_with_retries(self, mock_logger, error_handler):
        retry_func = Mock(side_effect=[Exception("Retry 1"), Exception("Retry 2"), "Success"])

        result = error_handler.handle_error(
            error=Exception("Initial error"),
            category=ErrorCategory.API_ERROR,
            severity=ErrorSeverity.HIGH,
            service="test_service",
            details={},
            retry_func=retry_func,
        )

        assert result == "Success"
        assert retry_func.call_count == 3
        assert mock_logger.called

    def test_error_handling_with_circuit_breaker(self, error_handler):
        service = "test_service"
        cb = error_handler._get_circuit_breaker(service)

        # Force circuit breaker to open
        for _ in range(5):
            error_handler.handle_error(
                error=Exception("Test error"),
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service=service,
                details={},
                retry_func=None,
            )

        # Next attempt should raise circuit breaker exception
        with pytest.raises(Exception) as exc_info:
            error_handler.handle_error(
                error=Exception("Test error"),
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service=service,
                details={},
                retry_func=None,
            )
        assert "Circuit breaker open" in str(exc_info.value)
