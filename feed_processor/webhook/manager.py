from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as tz
import time
import threading
import json
from typing import Dict, Any, Optional, List
import requests
import structlog
from feed_processor.metrics.prometheus import MetricsCollector

@dataclass
class WebhookResponse:
    """Response data for webhook deliveries"""
    success: bool
    status_code: int
    error_id: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = datetime.now(tz.utc).isoformat()

class WebhookManager:
    """Manages webhook delivery with rate limiting and retry logic"""
    
    def __init__(
        self,
        webhook_url: str,
        rate_limit: float = 0.2,
        max_retries: int = 3
    ):
        self.webhook_url = webhook_url
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.last_request_time = 0
        self.metrics = MetricsCollector()
        self._initialize_metrics()
        self._lock = threading.Lock()
        
        # Setup structured logging
        self.logger = structlog.get_logger(__name__).bind(
            component="WebhookManager",
            webhook_url=webhook_url,
            rate_limit=rate_limit,
            max_retries=max_retries
        )
        self.logger.info("webhook_manager_initialized")

    def _initialize_metrics(self):
        """Initialize webhook delivery metrics."""
        # Delivery metrics
        self.metrics.increment("webhook_requests", 0, labels={"status": "success"})
        self.metrics.increment("webhook_requests", 0, labels={"status": "failed"})
        self.metrics.increment("webhook_retries", 0)
        
        # Performance metrics
        self.metrics.record("webhook_latency", 0.0)
        self.metrics.set_gauge("rate_limit_delay", 0.0)
        
        # Batch metrics
        self.metrics.set_gauge("batch_size", 0)
        self.metrics.record("payload_size", 0)

    def _wait_for_rate_limit(self) -> None:
        """Enforce minimum interval between requests."""
        with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            
            if elapsed < self.rate_limit:
                sleep_time = self.rate_limit - elapsed
                self.logger.debug(
                    "rate_limit_delay",
                    sleep_time=sleep_time,
                    elapsed=elapsed
                )
                # Set last_request_time BEFORE sleeping to ensure accurate timing
                self.last_request_time = current_time + sleep_time
                self.metrics.set_gauge("rate_limit_delay", sleep_time)
                time.sleep(sleep_time)
            else:
                # If no sleep needed, set to current time
                self.last_request_time = current_time

    def _validate_payload(self, payload: Dict[str, Any]) -> None:
        """Validate webhook payload against required schema."""
        log = self.logger.bind(payload_id=payload.get("sourceMetadata", {}).get("feedId"))
        
        # Check required fields
        required_fields = {"title", "contentType", "brief"}
        missing_fields = required_fields - set(payload.keys())
        if missing_fields:
            log.warning(
                "payload_validation_failed",
                error="missing_fields",
                missing_fields=list(missing_fields),
                payload=payload
            )
            raise ValueError(f"Missing required fields: {missing_fields}")
                
        # Validate title length
        if len(payload["title"]) > 255:
            log.warning(
                "payload_validation_failed",
                error="title_too_long",
                length=len(payload["title"]),
                payload=payload
            )
            raise ValueError("Title too long")
                
        # Validate content type
        if not isinstance(payload["contentType"], list):
            log.warning(
                "payload_validation_failed",
                error="invalid_content_type_format",
                payload=payload
            )
            raise ValueError("Content type must be a list")
                
        valid_types = {"BLOG", "VIDEO", "SOCIAL"}
        invalid_types = set(payload["contentType"]) - valid_types
        if invalid_types:
            log.warning(
                "payload_validation_failed",
                error="invalid_content_types",
                invalid_types=list(invalid_types),
                payload=payload
            )
            raise ValueError(f"Invalid content types: {invalid_types}")
                
        # Validate brief length
        if len(payload["brief"]) > 2000:
            log.warning(
                "payload_validation_failed",
                error="brief_too_long",
                length=len(payload["brief"]),
                payload=payload
            )
            raise ValueError("Brief too long")
                
        log.debug("payload_validation_success", payload=payload)

    def _send_single_request(
        self,
        payload: Dict[str, Any],
        attempt: int = 1
    ) -> WebhookResponse:
        """Send a single webhook request with retry logic."""
        log = self.logger.bind(
            payload_id=payload.get("sourceMetadata", {}).get("feedId"),
            attempt=attempt
        )
        
        try:
            self._wait_for_rate_limit()
            
            log.debug("sending_webhook_request", payload=payload)
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 429:
                delay = self.rate_limit * 2
                log.warning(
                    "rate_limit_hit_adding_delay",
                    delay=delay,
                    status_code=response.status_code,
                    error=response.text
                )
                time.sleep(delay)
                if attempt < self.max_retries:
                    return self._send_single_request(payload, attempt + 1)
            
            elif response.status_code >= 500:
                if attempt < self.max_retries:
                    sleep_time = (2 ** attempt) * self.rate_limit
                    log.warning(
                        "webhook_request_failed_retrying",
                        status_code=response.status_code,
                        retry_attempt=attempt,
                        error=response.text
                    )
                    time.sleep(sleep_time)
                    return self._send_single_request(payload, attempt + 1)
                else:
                    error_id = f"err_{int(time.time())}_{response.status_code}"
                    log.error(
                        "webhook_request_failed_max_retries",
                        status_code=response.status_code,
                        error=response.text,
                        error_id=error_id
                    )
                    return WebhookResponse(
                        success=False,
                        status_code=response.status_code,
                        error_type="ServerError",
                        error_id=error_id
                    )
                    
            if 200 <= response.status_code < 300:
                log.info("webhook_request_success", status_code=response.status_code)
                self.metrics.increment("webhook_requests", labels={"status": "success"})
                return WebhookResponse(
                    success=True,
                    status_code=response.status_code
                )
            else:
                error_id = f"err_{int(time.time())}_{response.status_code}"
                log.error(
                    "webhook_request_failed",
                    status_code=response.status_code,
                    error=response.text,
                    error_id=error_id
                )
                self.metrics.increment("webhook_requests", labels={"status": "failed"})
                return WebhookResponse(
                    success=False,
                    status_code=response.status_code,
                    error_type="ClientError" if response.status_code < 500 else "ServerError",
                    error_id=error_id
                )
            
        except Exception as e:
            error_id = f"err_{int(time.time())}_{hash(str(e))}"
            
            if attempt < self.max_retries:
                sleep_time = (2 ** attempt) * self.rate_limit
                log.error(
                    "webhook_request_error_retrying",
                    error=str(e),
                    error_type=e.__class__.__name__,
                    retry_attempt=attempt
                )
                time.sleep(sleep_time)
                return self._send_single_request(payload, attempt + 1)
                
            log.error(
                "webhook_request_error_max_retries",
                error=str(e),
                error_type=e.__class__.__name__,
                error_id=error_id
            )
            self.metrics.increment("webhook_requests", labels={"status": "failed"})
            return WebhookResponse(
                success=False,
                status_code=500,
                error_type=e.__class__.__name__,
                error_id=error_id
            )

    def send_webhook(self, payload: Dict[str, Any]) -> WebhookResponse:
        """Send webhook with rate limiting and retries."""
        try:
            self._validate_payload(payload)
            timestamp: str = datetime.now(tz.utc).isoformat()
            payload_size = len(json.dumps(payload))
            self.metrics.record("payload_size", payload_size)
            self.metrics.set_gauge("batch_size", 1)
            start_time = time.time()
            response = self._send_single_request(payload)
            self.metrics.record("webhook_latency", time.time() - start_time)
            return response
            
        except ValueError as e:
            error_id = f"err_{int(time.time())}_validation"
            self.metrics.increment("webhook_requests", labels={"status": "failed"})
            return WebhookResponse(
                success=False,
                status_code=400,
                error_type="ValidationError",
                error_id=error_id
            )

    def bulk_send(self, payloads: List[Dict[str, Any]]) -> List[WebhookResponse]:
        """Send multiple webhooks with rate limiting."""
        self.logger.info("starting_bulk_send", payload_count=len(payloads))
        
        responses = []
        success_count = 0
        error_count = 0
        
        for payload in payloads:
            response = self.send_webhook(payload)
            responses.append(response)
            
            if response.success:
                success_count += 1
            else:
                error_count += 1
        
        self.logger.info(
            "bulk_send_completed",
            total_items=len(payloads),
            success_count=success_count,
            error_count=error_count
        )
        
        return responses
