"""Error handling module for feed processor."""

import logging
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional


class ErrorSeverity(Enum):
    """Error severity levels for prioritization and logging."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification and tracking."""

    API_ERROR = "api_error"
    PROCESSING_ERROR = "processing_error"
    DELIVERY_ERROR = "delivery_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SYSTEM_ERROR = "system_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for an error occurrence."""

    timestamp: str
    error_id: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: Dict[str, Any]
    retry_count: int
    max_retries: int


class CircuitBreaker:
    """Circuit breaker for protecting services from cascading failures."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        """Initialize circuit breaker with configurable thresholds.

        Args:
            failure_threshold: Number of failures before opening circuit
            reset_timeout: Seconds to wait before attempting reset
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"
        self._lock = threading.Lock()

    def __str__(self) -> str:
        """Return string representation of circuit breaker state."""
        return f"CircuitBreaker(state={self.state}, failures={self.failure_count})"

    def __repr__(self) -> str:
        """Return detailed string representation of circuit breaker."""
        return (
            f"CircuitBreaker(state={self.state}, "
            f"failures={self.failure_count}, "
            f"threshold={self.failure_threshold}, "
            f"timeout={self.reset_timeout})"
        )

    def __getstate__(self):
        """Return the state for pickling."""
        return {
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "state": self.state,
        }

    def __setstate__(self, state):
        """Set the state when unpickling."""
        self.failure_threshold = state["failure_threshold"]
        self.reset_timeout = state["reset_timeout"]
        self.failure_count = state["failure_count"]
        self.last_failure_time = state["last_failure_time"]
        self.state = state["state"]
        self._lock = threading.Lock()

    def can_proceed(self) -> bool:
        """Check if operation can proceed based on circuit state."""
        with self._lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                if time.time() - self.last_failure_time >= self.reset_timeout:
                    self.state = "half-open"
                    return True
                return False

            return self.state == "half-open"

    def record_failure(self) -> None:
        """Record a failure and update circuit state."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.failure_count = 0

    def record_success(self) -> None:
        """Record a success and potentially reset the circuit."""
        with self._lock:
            if self.state == "half-open" or self.state == "open":
                self.state = "closed"
            self.failure_count = 0
            self.last_failure_time = 0

    def reset(self) -> None:
        """Reset the circuit breaker state."""
        with self._lock:
            self.state = "closed"
            self.failure_count = 0
            self.last_failure_time = 0


class ErrorHandler:
    """Comprehensive error handler with circuit breaking and retry capabilities."""

    def __init__(self):
        """Initialize ErrorHandler with default configurations."""
        self.logger = logging.getLogger(__name__)
        self.error_counts: Dict[ErrorCategory, int] = {}
        self.error_history: deque = deque(maxlen=100)  # Default size
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.service_configs: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Service-specific configurations
        self.service_configs = {
            "inoreader": {
                "failure_threshold": 3,
                "reset_timeout": 120,
                "max_retries": {
                    ErrorCategory.RATE_LIMIT_ERROR: 5,
                    ErrorCategory.API_ERROR: 3,
                    ErrorCategory.SYSTEM_ERROR: 2,
                },
            },
            "webhook": {
                "failure_threshold": 5,
                "reset_timeout": 60,
                "max_retries": {
                    ErrorCategory.RATE_LIMIT_ERROR: 5,
                    ErrorCategory.DELIVERY_ERROR: 3,
                    ErrorCategory.SYSTEM_ERROR: 2,
                },
            },
            "test_service": {
                "failure_threshold": 3,
                "reset_timeout": 60,
                "max_retries": {ErrorCategory.PROCESSING_ERROR: 1, ErrorCategory.SYSTEM_ERROR: 1},
            },
        }

    def _get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        with self._lock:
            if service not in self.circuit_breakers:
                config = self.service_configs.get(service, {})
                failure_threshold = config.get("failure_threshold", 5)
                reset_timeout = config.get("reset_timeout", 60)
                self.circuit_breakers[service] = CircuitBreaker(
                    failure_threshold=failure_threshold, reset_timeout=reset_timeout
                )
            return self.circuit_breakers[service]

    def _get_max_retries(self, service: str, category: ErrorCategory) -> int:
        """Get maximum retry count for a service and error category."""
        config = self.service_configs.get(service, {})
        max_retries = config.get("max_retries", {})
        return max_retries.get(category, 0)

    def _create_error_context(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        details: Dict[str, Any],
    ) -> ErrorContext:
        """Create error context with tracking information."""
        timestamp = datetime.now().isoformat()
        error_id = f"ERR-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

        context = ErrorContext(
            timestamp=timestamp,
            error_id=error_id,
            severity=severity,
            category=category,
            message=str(error),
            details=details,
            retry_count=0,
            max_retries=1,
        )

        return context

    def _sanitize_message(self, message: str) -> str:
        """Sanitize error message by redacting sensitive information."""
        # Redact API keys
        message = re.sub(r"api_key=[\w\-]+", "api_key=[REDACTED]", message)
        # Redact passwords
        message = re.sub(r"password=[\w\-]+", "password=[REDACTED]", message)
        # Redact tokens
        message = re.sub(r"token=[\w\-]+", "token=[REDACTED]", message)
        return message

    def _format_system_log(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Format error for system logs with full details."""
        return {
            "error_id": error_context.error_id,
            "timestamp": error_context.timestamp,
            "severity": error_context.severity.value,
            "category": error_context.category.value,
            "message": error_context.message,
            "details": error_context.details,
            "retry_count": error_context.retry_count,
            "max_retries": error_context.max_retries,
        }

    def _format_airtable_log(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Format error for Airtable with limited sensitive data."""
        return {
            "error_id": error_context.error_id,
            "timestamp": error_context.timestamp,
            "severity": error_context.severity.value,
            "category": error_context.category.value,
            "message": self._sanitize_message(error_context.message),
            "retry_count": error_context.retry_count,
        }

    def _log_error(self, error_context: ErrorContext) -> None:
        """Log error with appropriate severity level."""
        log_data = self._format_system_log(error_context)

        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_data)
            self._notify_team(error_context)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(log_data)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_data)
        else:
            self.logger.info(log_data)

        self._log_to_airtable(self._format_airtable_log(error_context))

    def _log_to_airtable(self, log_data: Dict[str, Any]) -> None:
        """Log sanitized error data to Airtable."""
        # Implementation depends on Airtable configuration
        pass

    def _generate_error_id(self) -> str:
        """Generate a unique error ID."""
        timestamp = int(time.time() * 1000)
        random_suffix = random.randint(1000, 9999)
        return f"ERR-{timestamp}-{random_suffix}"

    def _calculate_backoff(self, retry_count: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff with jitter."""
        max_delay = base_delay * (2**retry_count)
        return random.uniform(0, min(max_delay, 60))

    def _notify_team(self, error_context: ErrorContext) -> None:
        """Send notifications for critical errors."""
        # Implementation depends on notification service configuration
        pass

    def get_error_metrics(self) -> Dict[str, Any]:
        """Get error tracking metrics."""
        return {
            "error_counts": {cat.value: self.error_counts.get(cat, 0) for cat in ErrorCategory},
            "error_history_size": len(self.error_history),
            "circuit_breaker_states": {
                service: breaker.state for service, breaker in self.circuit_breakers.items()
            },
        }

    def set_error_history_size(self, size: int) -> None:
        """Set the maximum size of error history."""
        if size <= 0:
            raise ValueError("Error history size must be positive")
        new_history = deque(self.error_history, maxlen=size)
        self.error_history = new_history

    def handle_error(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        service: str,
        details: Dict[str, Any],
        retry_func: Optional[Callable] = None,
    ) -> None:
        """Handle an error with retries and circuit breaking.

        Args:
            error: The exception that occurred
            category: Category of the error
            severity: Severity level of the error
            service: Service where the error occurred
            details: Additional error details
            retry_func: Optional function to retry on failure
        """
        # Create error context and update metrics first
        error_context = self._create_error_context(error, category, severity, details)
        error_context.max_retries = self._get_max_retries(service, category)

        # Update error counts using category as key
        if category not in self.error_counts:
            self.error_counts[category] = 0
        self.error_counts[category] += 1

        # Sanitize error message
        error_context.message = self._sanitize_message(str(error))

        # Add to error history
        self.error_history.append(error_context)

        self._log_error(error_context)

        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(service)
        if not circuit_breaker.can_proceed():
            self.error_history.pop()  # Remove error if circuit breaker is open
            raise Exception(f"Circuit breaker open for service: {service}")

        # Handle retries if available
        if retry_func and error_context.retry_count < error_context.max_retries:
            try:
                for _ in range(error_context.max_retries):
                    try:
                        result = retry_func()
                        circuit_breaker.record_success()
                        return result
                    except Exception:
                        error_context.retry_count += 1
                        if error_context.retry_count >= error_context.max_retries:
                            circuit_breaker.record_failure()
                            raise
                        time.sleep(self._calculate_backoff(error_context.retry_count))
            except Exception as e:
                circuit_breaker.record_failure()
                raise e
        else:
            circuit_breaker.record_failure()
            raise error

    def reset_circuit_breaker(self, service: str) -> None:
        """Manually reset a circuit breaker."""
        if service in self.circuit_breakers:
            self.circuit_breakers[service].reset()


class BaseError(Exception):
    """Base exception class for all feed processor errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize base error with optional context.

        Args:
            message: Error message
            context: Optional error context
        """
        super().__init__(message)
        self.context = context or {}

    def __str__(self) -> str:
        """Return string representation of error."""
        return str(super().__str__())

    def __repr__(self) -> str:
        """Return detailed string representation of error."""
        return f"{self.__class__.__name__}({super().__str__()}, context={self.context})"


class APIError(BaseError):
    """Use this error when API operations fail."""

    pass


class ProcessingError(BaseError):
    """Use this error when content processing fails."""

    pass


class FeedProcessingError(BaseError):
    """Use this error when feed processing operations fail."""

    pass


class WebhookError(BaseError):
    """Use this error when webhook delivery fails."""

    pass


class ValidationError(BaseError):
    """Use this error when data validation fails."""

    pass


class RateLimitError(BaseError):
    """Use this error when rate limits are exceeded."""

    pass


class NetworkError(BaseError):
    """Use this error when network operations fail."""

    pass


class ConfigurationError(BaseError):
    """Use this error when configuration is invalid."""

    pass


def handle_errors(
    category: ErrorCategory,
    severity: ErrorSeverity,
    service: str,
    error_handler: Optional[ErrorHandler] = None,
):
    """Handle errors in decorated functions with circuit breaking and retries.

    Args:
        category: Category of errors to handle
        severity: Severity level of errors
        service: Service name for circuit breaking
        error_handler: Optional custom error handler
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler.handle_error(
                    error=e,
                    category=category,
                    severity=severity,
                    service=service,
                    details={"args": args, "kwargs": kwargs},
                )
                raise

        return wrapper

    return decorator
