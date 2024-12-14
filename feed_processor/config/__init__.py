"""Configuration management for feed processor components."""

from .processor_config import ProcessorConfig
from .webhook_config import WebhookConfig

# Create and expose default settings
settings = ProcessorConfig()

__all__ = ["ProcessorConfig", "WebhookConfig", "settings"]
