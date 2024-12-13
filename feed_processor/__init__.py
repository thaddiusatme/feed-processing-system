"""Feed processor module."""

from .metrics import init_metrics, start_metrics_server
from .processor import FeedProcessor
from .validator import FeedValidator
from .webhook import WebhookConfig, WebhookManager

__version__ = "1.0.0"
