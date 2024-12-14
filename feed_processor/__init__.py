"""Feed processor module."""

from .config.webhook_config import WebhookConfig
from .core.processor import FeedProcessor
from .metrics import init_metrics, start_metrics_server
from .queues.content import ContentQueue, QueuedContent
from .validation.validators import FeedValidator
from .webhook.manager import WebhookManager, WebhookResponse

__version__ = "1.0.0"

__all__ = ["FeedProcessor", "ContentQueue", "QueuedContent", "WebhookManager", "WebhookResponse"]
