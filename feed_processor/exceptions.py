"""
Custom exceptions for feed processing system.
"""


class FeedProcessorError(Exception):
    """Base exception for feed processor errors."""

    pass


class ValidationError(FeedProcessorError):
    """Raised when feed data fails validation."""

    pass


class WebhookError(FeedProcessorError):
    """Raised when there is an error processing a webhook."""

    pass


class RateLimitError(FeedProcessorError):
    """Raised when rate limit is exceeded."""

    pass


class StorageError(FeedProcessorError):
    """Raised when there is an error with Google Drive storage."""

    pass
