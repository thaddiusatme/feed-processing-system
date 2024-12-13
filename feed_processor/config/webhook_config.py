"""Configuration settings for webhook functionality."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class WebhookConfig:
    """Configuration for webhook delivery.

    Attributes:
        retry_attempts: Maximum number of retry attempts for failed deliveries
        timeout: Request timeout in seconds
        max_concurrent: Maximum number of concurrent webhook deliveries
        rate_limit: Minimum seconds between webhook requests
        batch_size: Maximum items per webhook delivery
        auth_token: Optional authentication token for webhook requests
    """

    retry_attempts: int = 3
    timeout: int = 30
    max_concurrent: int = 10
    rate_limit: float = 0.2
    batch_size: int = 100
    auth_token: str = ""

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "WebhookConfig":
        """Create a WebhookConfig instance from a dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            WebhookConfig instance with values from dictionary
        """
        return cls(**{
            k: v for k, v in config_dict.items()
            if k in cls.__dataclass_fields__
        })
