from dataclasses import dataclass
from datetime import datetime, timezone, time
from enum import Enum
import logging
import random
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Deque
import threading
from functools import wraps
import os
from collections import deque
import re

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    API_ERROR = "api_error"
    PROCESSING_ERROR = "processing_error"
    DELIVERY_ERROR = "delivery_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SYSTEM_ERROR = "system_error"

@dataclass
class ErrorContext:
    timestamp: str
    error_id: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 0

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"
        self._lock = threading.Lock()

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "open"

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.state = "closed"

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        
        if time.time() - self.last_failure_time >= self.reset_timeout:
            with self._lock:
                self.state = "half-open"
                return True
        
        return False

class ErrorHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self.error_history: Deque[ErrorContext] = deque(maxlen=int(os.getenv('ERROR_HISTORY_SIZE', '100')))
        
        # Service-specific configurations
        self.service_configs = {
            'inoreader': {
                'failure_threshold': 3,  # More sensitive threshold for API
                'reset_timeout': 120,    # Longer recovery time
                'max_retries': {
                    ErrorCategory.RATE_LIMIT_ERROR: 5,
                    ErrorCategory.API_ERROR: 3,
                    ErrorCategory.SYSTEM_ERROR: 2
                }
            },
            'webhook': {
                'failure_threshold': 5,
                'reset_timeout': 60,
                'max_retries': {
                    ErrorCategory.RATE_LIMIT_ERROR: 5,
                    ErrorCategory.DELIVERY_ERROR: 3,
                    ErrorCategory.SYSTEM_ERROR: 2
                }
            }
        }

    def _get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create a circuit breaker with service-specific config"""
        with self._lock:
            if service not in self.circuit_breakers:
                config = self.service_configs.get(service, {})
                self.circuit_breakers[service] = CircuitBreaker(
                    failure_threshold=config.get('failure_threshold', 5),
                    reset_timeout=config.get('reset_timeout', 60)
                )
            return self.circuit_breakers[service]

    def _get_max_retries(self, service: str, category: ErrorCategory) -> int:
        """Get max retries based on service and error category"""
        service_config = self.service_configs.get(service, {})
        retry_config = service_config.get('max_retries', {})
        return retry_config.get(category, 3)  # Default to 3 retries

    def _create_error_context(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        details: Dict[str, Any]
    ) -> ErrorContext:
        """Create error context with service-specific retry configuration"""
        service = details.get('service', 'default')
        max_retries = self._get_max_retries(service, category)
        
        return ErrorContext(
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_id=self._generate_error_id(),
            severity=severity,
            category=category,
            message=str(error),
            details=details,
            max_retries=max_retries
        )

    def _format_system_log(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Format error for system logs (full details)"""
        return {
            "error_id": error_context.error_id,
            "timestamp": error_context.timestamp,
            "severity": error_context.severity.value,
            "category": error_context.category.value,
            "message": error_context.message,
            "details": error_context.details,
            "retry_count": error_context.retry_count
        }

    def _format_airtable_log(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Format error for Airtable (limited sensitive data)"""
        # Filter out sensitive fields
        safe_details = {
            k: v for k, v in error_context.details.items()
            if k not in {'api_key', 'token', 'password', 'user_id'}
        }
        
        return {
            "error_id": error_context.error_id,
            "timestamp": error_context.timestamp,
            "severity": error_context.severity.value,
            "category": error_context.category.value,
            "message": self._sanitize_message(error_context.message),
            "details": safe_details
        }

    def _sanitize_message(self, message: str) -> str:
        """Remove sensitive information from error messages"""
        # Add patterns for sensitive data
        patterns = [
            r'key=[\w-]+',
            r'token=[\w-]+',
            r'password=[\w-]+',
            r'api_key=[\w-]+'
        ]
        
        sanitized = message
        for pattern in patterns:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized)
        return sanitized

    def _log_error(self, error_context: ErrorContext) -> None:
        """Enhanced error logging with different detail levels"""
        # System logs get full details
        system_log = self._format_system_log(error_context)
        
        # Airtable logs get sanitized details
        airtable_log = self._format_airtable_log(error_context)
        
        # Track error history
        self.error_history.append(error_context)
        
        # Log based on severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(system_log)
            self._notify_team(error_context)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(system_log)
            if error_context.category in [ErrorCategory.API_ERROR, ErrorCategory.DELIVERY_ERROR]:
                self._notify_team(error_context)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(system_log)
        else:
            self.logger.info(system_log)
            
        # Log to Airtable with sanitized data
        self._log_to_airtable(airtable_log)

    def _log_to_airtable(self, log_data: Dict[str, Any]) -> None:
        """Log sanitized error data to Airtable"""
        # Implementation depends on your Airtable integration
        pass

    def _generate_error_id(self) -> str:
        """Generate a unique error ID."""
        return f"err_{int(time.time())}_{random.randint(1000, 9999)}"

    def _calculate_backoff(self, retry_count: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff with jitter."""
        max_delay = base_delay * (2 ** retry_count)
        jitter = random.uniform(0, 0.1 * max_delay)
        return min(max_delay + jitter, 30)  # Cap at 30 seconds

    def handle_error(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        service: str,
        details: Dict[str, Any],
        retry_func: Optional[Callable] = None
    ) -> Optional[Any]:
        """Handle an error with retries and circuit breaking."""
        circuit_breaker = self._get_circuit_breaker(service)
        
        if not circuit_breaker.can_execute():
            raise Exception(f"Circuit breaker open for service: {service}")

        error_context = self._create_error_context(error, category, severity, details)
        self._log_error(error_context)

        if retry_func and error_context.retry_count < error_context.max_retries:
            return self._handle_retry(error_context, retry_func, circuit_breaker, service)
        
        circuit_breaker.record_failure()
        return None

    def _handle_retry(
        self,
        error_context: ErrorContext,
        retry_func: Callable,
        circuit_breaker: CircuitBreaker,
        service: str
    ) -> Optional[Any]:
        """Handle retry logic with exponential backoff."""
        while error_context.retry_count < error_context.max_retries:
            backoff_delay = self._calculate_backoff(error_context.retry_count)
            self.logger.info(
                f"Retrying after {backoff_delay:.2f}s "
                f"(attempt {error_context.retry_count + 1}/{error_context.max_retries})"
            )
            
            time.sleep(backoff_delay)
            
            try:
                result = retry_func()
                circuit_breaker.record_success()
                return result
            except Exception as retry_error:
                error_context.retry_count += 1
                error_context.message = str(retry_error)
                self._log_error(error_context)

        circuit_breaker.record_failure()
        return None

    def _notify_team(self, error_context: ErrorContext) -> None:
        """Send notifications for critical errors"""
        # Implementation depends on your notification system
        # Could be Slack, email, PagerDuty, etc.
        pass

    def reset_circuit_breaker(self, service: str) -> None:
        """Manually reset a circuit breaker (for admin use)"""
        with self._lock:
            if service in self.circuit_breakers:
                self.circuit_breakers[service].record_success()
                self.logger.info(f"Circuit breaker manually reset for service: {service}")

    def get_error_metrics(self) -> Dict[str, Any]:
        """Get error metrics for monitoring"""
        metrics = {
            "total_errors": len(self.error_history),
            "errors_by_category": {},
            "errors_by_severity": {},
            "circuit_breaker_states": {}
        }
        
        # Calculate error distributions
        for error in self.error_history:
            metrics["errors_by_category"][error.category.value] = \
                metrics["errors_by_category"].get(error.category.value, 0) + 1
            metrics["errors_by_severity"][error.severity.value] = \
                metrics["errors_by_severity"].get(error.severity.value, 0) + 1
        
        # Get circuit breaker states
        for service, cb in self.circuit_breakers.items():
            metrics["circuit_breaker_states"][service] = {
                "state": cb.state,
                "failures": cb.failures
            }
        
        return metrics

def handle_errors(
    category: ErrorCategory,
    severity: ErrorSeverity,
    service: str,
    error_handler: ErrorHandler
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                details = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                return error_handler.handle_error(
                    error=e,
                    category=category,
                    severity=severity,
                    service=service,
                    details=details,
                    retry_func=lambda: func(*args, **kwargs)
                )
        return wrapper
    return decorator
