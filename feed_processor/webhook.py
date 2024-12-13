from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import time
import json
import requests
from datetime import datetime
import re


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


@dataclass
class WebhookConfig:
    endpoint: str
    auth_token: str
    max_retries: int = 3
    retry_delay: int = 1
    timeout: int = 5
    batch_size: int = 10

    def __post_init__(self):
        # Validate endpoint URL
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(self.endpoint):
            raise ValueError("Invalid webhook endpoint URL")


@dataclass
class WebhookResponse:
    success: bool
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    rate_limited: bool = False
    response_data: Optional[Dict[str, Any]] = None


class WebhookError(Exception):
    """Custom exception for webhook-related errors."""

    pass


class WebhookManager:
    def __init__(self, config: WebhookConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {config.auth_token}", "Content-Type": "application/json"}
        )

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate webhook payload before sending."""
        required_fields = ["type", "title", "link"]
        return all(field in payload for field in required_fields)

    def send(self, feed_data: Dict[str, Any]) -> WebhookResponse:
        """Send a single feed to the webhook endpoint."""
        if not self.validate_payload(feed_data):
            raise WebhookError("Invalid payload: missing required fields")

        retry_count = 0
        while retry_count <= self.config.max_retries:
            try:
                response = requests.post(
                    self.config.endpoint,
                    headers=self.session.headers,
                    json=feed_data,
                    timeout=self.config.timeout,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self.config.retry_delay))
                    time.sleep(retry_after)
                    return WebhookResponse(
                        success=False,
                        status_code=429,
                        error_message="Rate limit exceeded",
                        retry_count=retry_count,
                        rate_limited=True,
                    )

                # Handle authentication errors
                if response.status_code == 401:
                    return WebhookResponse(
                        success=False,
                        status_code=401,
                        error_message="Authentication failed",
                        retry_count=retry_count,
                    )

                if response.status_code == 200:
                    return WebhookResponse(
                        success=True,
                        status_code=200,
                        retry_count=retry_count,
                        response_data=response.json(),
                    )

                # For other errors, retry after delay if we haven't exceeded max retries
                if retry_count < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    retry_count += 1
                    continue

                # Max retries exceeded
                return WebhookResponse(
                    success=False,
                    status_code=response.status_code,
                    error_message="Max retries exceeded",
                    retry_count=retry_count,
                )

            except requests.RequestException as e:
                if retry_count < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    retry_count += 1
                    continue

                return WebhookResponse(success=False, error_message=str(e), retry_count=retry_count)

    def batch_send(self, feeds: List[Dict[str, Any]]) -> List[WebhookResponse]:
        """Send multiple feeds in batches."""
        responses = []
        for i in range(0, len(feeds), self.config.batch_size):
            batch = feeds[i : i + self.config.batch_size]
            try:
                response = requests.post(
                    self.config.endpoint,
                    headers=self.session.headers,
                    json={"feeds": batch},
                    timeout=self.config.timeout,
                )

                if response.status_code == 200:
                    responses.append(
                        WebhookResponse(
                            success=True,
                            status_code=response.status_code,
                            response_data=response.json(),
                        )
                    )
                else:
                    responses.append(
                        WebhookResponse(
                            success=False,
                            status_code=response.status_code,
                            error_message=f"HTTP {response.status_code}",
                        )
                    )

            except requests.RequestException as e:
                responses.append(WebhookResponse(success=False, error_message=str(e)))

        return responses
