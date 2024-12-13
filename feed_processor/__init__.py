"""Feed processor module."""

from .metrics import init_metrics, start_metrics_server
from .core.processor import FeedProcessor
from .validation.validators import FeedValidator
from .webhook.manager import WebhookManager
from .config.webhook_config import WebhookConfig

__version__ = "1.0.0"
