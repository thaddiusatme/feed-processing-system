"""Error handling module for the feed processing system.

This module provides a comprehensive set of custom exceptions and error handlers
for managing various error scenarios in feed processing, validation, and delivery.
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorCategory(Enum):
    """Error categories for classification and tracking."""

    NETWORK = "network"
    VALIDATION = "validation"
    PROCESSING = "processing"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels for prioritization and logging."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorHandler:
    """Error handler for tracking and logging errors.

    This class provides methods for handling errors, logging error information,
    and tracking error counts.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize ErrorHandler.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.error_counts: Dict[ErrorCategory, int] = {cat: 0 for cat in ErrorCategory}
        self.error_history: List[Dict[str, Any]] = []

    def handle_error(
        self, error: Exception, category: ErrorCategory, severity: ErrorSeverity
    ) -> None:
        """Handle an error and update error counts and history.

        Args:
            error: Error instance
            category: Error category
            severity: Error severity
        """
        self.error_counts[category] += 1
        error_info = {
            "timestamp": time.time(),
            "error": str(error),
            "category": category,
            "severity": severity,
        }
        self.error_history.append(error_info)
        self._log_error(error_info)

    def _log_error(self, error_info: Dict[str, Any]) -> None:
        """Log an error with the provided information.

        Args:
            error_info: Dictionary containing error information
        """
        log_message = (
            f"Error: {error_info['error']} "
            f"Category: {error_info['category'].value} "
            f"Severity: {error_info['severity'].value}"
        )
        if error_info["severity"] in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self.logger.error(log_message)
        else:
            self.logger.warning(log_message)

    def get_error_count(self, category: Optional[ErrorCategory] = None) -> int:
        """Get the error count for a specific category or overall.

        Args:
            category: Optional error category

        Returns:
            Error count
        """
        if category is None:
            return sum(self.error_counts.values())
        return self.error_counts[category]

    def clear_history(self) -> None:
        """Clear the error history and reset error counts."""
        self.error_history.clear()
        self.error_counts = {cat: 0 for cat in ErrorCategory}


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures.

    This class provides methods for tracking failures and determining whether
    to proceed with an operation.
    """

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        """Initialize CircuitBreaker.

        Args:
            failure_threshold: Number of failures before opening the circuit
            reset_timeout: Time to wait before resetting the circuit
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.is_open = False

    def record_failure(self) -> None:
        """Record a failure and update the circuit state."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True

    def record_success(self) -> None:
        """Record a success and reset the circuit state."""
        self.failure_count = 0
        self.is_open = False

    def can_proceed(self) -> bool:
        """Determine whether to proceed with an operation.

        Returns:
            True if the circuit is closed, False otherwise
        """
        if not self.is_open:
            return True

        if time.time() - self.last_failure_time >= self.reset_timeout:
            self.is_open = False
            self.failure_count = 0
            return True

        return False

    def reset(self) -> None:
        """Reset the circuit state."""
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.is_open = False
