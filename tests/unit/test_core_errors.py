"""
Component: Error Handling.

ID: TEST-ERR-001
Category: Core Error Handling

Purpose:
Test the consolidated error handling system including circuit breakers,
error tracking, and retry mechanisms.

AI Testing Considerations:
1. Thread safety in concurrent operations
2. Memory usage in error tracking
3. Retry backoff patterns
4. Circuit breaker state transitions
"""

import threading
import time

import pytest

from feed_processor.core.errors import CircuitBreaker, ErrorCategory, ErrorHandler, ErrorSeverity


class TestCircuitBreaker:
    """Test suite for CircuitBreaker functionality."""

    def test_initial_state(self):
        """Test initial state of circuit breaker."""
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.last_failure_time == 0

    def test_failure_threshold(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=60)

        # Record failures up to threshold
        for _ in range(3):
            cb.record_failure()

        assert cb.state == "open"
        assert cb.can_proceed() is False

    def test_reset_timeout(self):
        """Test circuit transitions to half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=1)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Wait for reset timeout
        time.sleep(1.1)
        assert cb.can_proceed() is True
        assert cb.state == "half-open"

    def test_success_resets_circuit(self):
        """Test successful operation resets circuit."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=1)

        # Force circuit to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # Wait for reset timeout
        time.sleep(1.1)

        # Check if circuit transitions to half-open
        assert cb.can_proceed() is True
        assert cb.state == "half-open"

        # Record success
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_thread_safety(self):
        """Test thread safety of circuit breaker."""
        cb = CircuitBreaker()
        threads = []
        for _ in range(200):
            thread = threading.Thread(target=cb.record_failure)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert cb.state == "open"


class TestErrorHandler:
    """Test suite for ErrorHandler functionality."""

    @pytest.fixture
    def error_handler(self):
        """Create a test error handler."""
        return ErrorHandler()

    def test_error_tracking(self, error_handler):
        """Test error tracking and metrics."""
        # Handle test error
        test_error = ValueError("Test error")
        try:
            error_handler.handle_error(
                error=test_error,
                category=ErrorCategory.PROCESSING_ERROR,
                severity=ErrorSeverity.HIGH,
                service="test_service",
                details={"test": "details"},
            )
        except ValueError:
            pass  # Expected error

        # Verify error was tracked
        metrics = error_handler.get_error_metrics()
        assert metrics["error_counts"][ErrorCategory.PROCESSING_ERROR.value] == 1

        # Verify error history
        assert len(error_handler.error_history) == 1
        error_context = error_handler.error_history[0]
        assert error_context.category == ErrorCategory.PROCESSING_ERROR
        assert error_context.severity == ErrorSeverity.HIGH
        assert error_context.message == "Test error"

    def test_circuit_breaker_integration(self, error_handler):
        """Test circuit breaker integration."""
        # Configure service with low threshold
        error_handler.service_configs["test_service"] = {
            "failure_threshold": 2,
            "reset_timeout": 60,
            "max_retries": {ErrorCategory.PROCESSING_ERROR: 1},
        }

        # Generate errors to trigger circuit breaker
        test_error = ValueError("Test error")
        for _ in range(3):
            with pytest.raises(Exception) as exc_info:
                error_handler.handle_error(
                    error=test_error,
                    category=ErrorCategory.PROCESSING_ERROR,
                    severity=ErrorSeverity.HIGH,
                    service="test_service",
                    details={},
                )

        # Verify circuit is open
        assert "Circuit breaker open" in str(exc_info.value)

    def test_retry_mechanism(self, error_handler):
        """Test retry mechanism with exponential backoff."""
        retry_count = 0

        def retry_func():
            nonlocal retry_count
            retry_count += 1
            if retry_count < 3:
                raise ValueError("Retry needed")

        # Handle error with retry function
        error_handler.handle_error(
            error=ValueError("Initial error"),
            category=ErrorCategory.API_ERROR,
            severity=ErrorSeverity.MEDIUM,
            service="inoreader",  # Uses service-specific config
            details={},
            retry_func=retry_func,
        )

        # Verify retries occurred
        assert retry_count == 3

    def test_error_sanitization(self, error_handler):
        """Test sensitive data sanitization."""
        error_msg = "API request failed with api_key=secret123"
        error = ValueError(error_msg)

        try:
            error_handler.handle_error(
                error=error,
                category=ErrorCategory.API_ERROR,
                severity=ErrorSeverity.HIGH,
                service="test_service",
                details={},
            )
        except ValueError:
            pass  # Expected error

        # Verify sensitive data was redacted
        error_context = error_handler.error_history[0]
        assert "api_key=[REDACTED]" in error_context.message
        assert "secret123" not in error_context.message

    def test_memory_management(self, error_handler):
        """Test error history size management."""
        # Override error history size
        error_handler.set_error_history_size(5)

        # Configure service with high threshold
        error_handler.service_configs["test_service"] = {
            "failure_threshold": 20,  # High threshold
            "reset_timeout": 60,
            "max_retries": {ErrorCategory.SYSTEM_ERROR: 1},
        }

        # Generate more errors than history size
        for i in range(10):
            try:
                error_handler.handle_error(
                    error=ValueError(f"Error {i}"),
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.LOW,
                    service="test_service",
                    details={},
                )
            except ValueError:
                pass  # Expected error

        # Verify history size is maintained
        assert len(error_handler.error_history) == 5

        # Verify we have the most recent errors
        messages = [e.message for e in error_handler.error_history]
        assert "Error 9" in messages
        assert "Error 0" not in messages

    def test_error_handling_integration(self):
        """Test integration of custom exceptions with ErrorHandler."""
        from feed_processor.core.errors import (
            ErrorCategory,
            ErrorHandler,
            ErrorSeverity,
            FeedProcessingError,
        )

        handler = ErrorHandler()
        error = FeedProcessingError("Test error")

        # Handle custom exception
        with pytest.raises(FeedProcessingError):
            handler.handle_error(
                error=error,
                category=ErrorCategory.PROCESSING_ERROR,
                severity=ErrorSeverity.HIGH,
                service="test_service",
                details={},
            )

        # Verify error was tracked correctly
        metrics = handler.get_error_metrics()
        assert metrics["error_counts"][ErrorCategory.PROCESSING_ERROR.value] == 1


class TestCustomExceptions:
    """Test suite for custom exception hierarchy."""

    def test_base_error(self):
        """Test BaseError is parent of all custom exceptions."""
        from feed_processor.core.errors import (
            BaseError,
            ConfigurationError,
            FeedProcessingError,
            NetworkError,
            RateLimitError,
            ValidationError,
            WebhookError,
        )

        # Test all custom exceptions inherit from BaseError
        assert issubclass(FeedProcessingError, BaseError)
        assert issubclass(WebhookError, BaseError)
        assert issubclass(ValidationError, BaseError)
        assert issubclass(RateLimitError, BaseError)
        assert issubclass(NetworkError, BaseError)
        assert issubclass(ConfigurationError, BaseError)

    def test_exception_messages(self):
        """Test exception messages are properly set."""
        from feed_processor.core.errors import FeedProcessingError, ValidationError, WebhookError

        # Test error messages
        feed_error = FeedProcessingError("Feed processing failed")
        assert str(feed_error) == "Feed processing failed"

        webhook_error = WebhookError("Webhook delivery failed")
        assert str(webhook_error) == "Webhook delivery failed"

        validation_error = ValidationError("Invalid data format")
        assert str(validation_error) == "Invalid data format"

    def test_error_with_context(self):
        """Test exceptions can carry additional context."""
        from feed_processor.core.errors import FeedProcessingError

        context = {"feed_id": "123", "timestamp": "2024-12-13"}
        error = FeedProcessingError("Processing failed", context=context)

        assert str(error) == "Processing failed"
        assert hasattr(error, "context")
        assert error.context == context

    def test_error_handling_integration(self):
        """Test integration of custom exceptions with ErrorHandler."""
        from feed_processor.core.errors import (
            ErrorCategory,
            ErrorHandler,
            ErrorSeverity,
            FeedProcessingError,
        )

        handler = ErrorHandler()
        error = FeedProcessingError("Test error")

        # Handle custom exception
        try:
            handler.handle_error(
                error=error,
                category=ErrorCategory.PROCESSING_ERROR,
                severity=ErrorSeverity.HIGH,
                service="test_service",
                details={},
            )
        except FeedProcessingError:
            pass  # Expected error

        # Verify error was tracked correctly
        metrics = handler.get_error_metrics()
        assert metrics["error_counts"][ErrorCategory.PROCESSING_ERROR.value] == 1
