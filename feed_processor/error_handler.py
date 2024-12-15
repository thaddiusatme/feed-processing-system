"""Error handling module for feed processor."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handler for processing errors."""

    def __init__(self):
        """Initialize error handler."""
        pass

    def handle_error(self, error: Exception, context: Optional[dict] = None) -> None:
        """Handle an error.

        Args:
            error: The error to handle
            context: Optional context about the error
        """
        if context is None:
            context = {}

        logger.error(f"Error occurred: {str(error)}", extra=context)
