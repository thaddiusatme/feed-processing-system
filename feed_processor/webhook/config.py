"""Webhook configuration module."""

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class WebhookConfig:
    """Configuration for webhook delivery.

    Attributes:
        url: Webhook endpoint URL
        auth_token: Optional authentication token
        headers: Optional custom headers
        rate_limit: Requests per second limit
        max_retries: Maximum retry attempts
        retry_delay: Base delay between retries (exponential backoff)
        timeout: Request timeout in seconds
    """

    url: str
    auth_token: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    rate_limit: float = 0.2  # 5 requests per second
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "WebhookConfig":
        """Create config from environment variables.

        Environment Variables:
            WEBHOOK_URL: Required webhook URL
            WEBHOOK_AUTH_TOKEN: Optional auth token
            WEBHOOK_RATE_LIMIT: Optional rate limit (requests/sec)
            WEBHOOK_MAX_RETRIES: Optional max retries
            WEBHOOK_RETRY_DELAY: Optional base retry delay
            WEBHOOK_TIMEOUT: Optional request timeout

        Returns:
            WebhookConfig instance

        Raises:
            ValueError: If required WEBHOOK_URL is missing
        """
        url = os.getenv("WEBHOOK_URL")
        if not url:
            raise ValueError("WEBHOOK_URL environment variable is required")

        return cls(
            url=url,
            auth_token=os.getenv("WEBHOOK_AUTH_TOKEN"),
            rate_limit=float(os.getenv("WEBHOOK_RATE_LIMIT", "0.2")),
            max_retries=int(os.getenv("WEBHOOK_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("WEBHOOK_RETRY_DELAY", "1.0")),
            timeout=float(os.getenv("WEBHOOK_TIMEOUT", "5.0")),
        )
