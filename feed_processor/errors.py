"""Error definitions for the feed processing system."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(Enum):
    """Categories of errors that can occur in the system."""

    VALIDATION_ERROR = "validation_error"
    API_ERROR = "api_error"
    PROCESSING_ERROR = "processing_error"
    STORAGE_ERROR = "storage_error"
    WEBHOOK_ERROR = "webhook_error"
    SYSTEM_ERROR = "system_error"


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseError(Exception):
    """Base error class for all feed processor errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize base error.

        Args:
            message: Error message
            category: Error category
            severity: Error severity
            error_id: Optional unique error ID
            details: Optional error details
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_id = error_id
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()


class ValidationError(BaseError):
    """Error raised when feed validation fails."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.LOW,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation error."""
        super().__init__(
            message,
            ErrorCategory.VALIDATION_ERROR,
            severity,
            error_id,
            details,
        )


class APIError(BaseError):
    """Error raised when API requests fail."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize API error."""
        super().__init__(
            message,
            ErrorCategory.API_ERROR,
            severity,
            error_id,
            details,
        )


class ProcessingError(BaseError):
    """Error raised during feed processing."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize processing error."""
        super().__init__(
            message,
            ErrorCategory.PROCESSING_ERROR,
            severity,
            error_id,
            details,
        )


class StorageError(BaseError):
    """Error raised when storage operations fail."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize storage error."""
        super().__init__(
            message,
            ErrorCategory.STORAGE_ERROR,
            severity,
            error_id,
            details,
        )


class WebhookError(BaseError):
    """Error raised when webhook operations fail."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize webhook error."""
        super().__init__(
            message,
            ErrorCategory.WEBHOOK_ERROR,
            severity,
            error_id,
            details,
        )


class SystemError(BaseError):
    """Error raised for system-level failures."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.CRITICAL,
        error_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize system error."""
        super().__init__(
            message,
            ErrorCategory.SYSTEM_ERROR,
            severity,
            error_id,
            details,
        )
