# Error Handling System

## Overview
The feed processing system uses a comprehensive error handling system that includes circuit breaking, error tracking, and retry mechanisms. The system is designed to be robust, maintainable, and provide detailed error information for debugging and monitoring.

## Components

### Error Classes
All custom exceptions inherit from `BaseError`:
- `FeedProcessingError`: Base exception for feed processing errors
- `WebhookError`: Exception for webhook-related errors
- `ValidationError`: Exception for validation errors
- `RateLimitError`: Exception for rate limit issues
- `NetworkError`: Exception for network-related errors
- `ConfigurationError`: Exception for configuration issues

### Error Categories (ErrorCategory)
- `API_ERROR`: API-related errors
- `PROCESSING_ERROR`: Feed processing errors
- `DELIVERY_ERROR`: Webhook delivery errors
- `RATE_LIMIT_ERROR`: Rate limiting issues
- `SYSTEM_ERROR`: System-level errors
- `VALIDATION_ERROR`: Data validation errors
- `NETWORK_ERROR`: Network connectivity issues
- `UNKNOWN`: Unclassified errors

### Error Severity Levels (ErrorSeverity)
- `LOW`: Minor issues that don't affect core functionality
- `MEDIUM`: Issues that may affect some operations
- `HIGH`: Serious issues requiring attention
- `CRITICAL`: System-breaking issues requiring immediate attention

### Circuit Breaker
The `CircuitBreaker` class implements the Circuit Breaker pattern to prevent cascading failures:
- States: closed, open, half-open
- Configurable failure threshold and reset timeout
- Thread-safe operations

### Error Handler
The `ErrorHandler` class provides comprehensive error management:
- Error tracking and metrics
- Service-specific configurations
- Retry mechanisms with exponential backoff
- Error sanitization for sensitive data
- Team notifications for critical errors

## Usage

### Basic Error Handling
```python
from feed_processor.core.errors import FeedProcessingError, ErrorCategory, ErrorSeverity

try:
    # Your code here
    process_feed(data)
except FeedProcessingError as e:
    error_handler.handle_error(
        error=e,
        category=ErrorCategory.PROCESSING_ERROR,
        severity=ErrorSeverity.HIGH,
        service="feed_processor",
        details={"feed_id": feed_id}
    )
```

### Using the Decorator
```python
from feed_processor.core.errors import handle_errors, ErrorCategory, ErrorSeverity

@handle_errors(
    category=ErrorCategory.API_ERROR,
    severity=ErrorSeverity.MEDIUM,
    service="inoreader"
)
def fetch_feed(feed_id: str):
    # Your code here
    pass
```

## Best Practices
1. Always use appropriate error categories and severity levels
2. Include relevant context in error details
3. Avoid exposing sensitive information in error messages
4. Use circuit breakers for external service calls
5. Configure appropriate retry strategies for different error types
