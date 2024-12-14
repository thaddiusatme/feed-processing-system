"""Feed processor module."""

from .config.webhook_config import WebhookConfig
from .core.processor import FeedProcessor
from .metrics import init_metrics, start_metrics_server
from .validation.validators import FeedValidator
from .webhook.manager import WebhookManager

__version__ = "1.0.0"
