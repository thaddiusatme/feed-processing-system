"""Notification system for alerting on pipeline events."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from ..metrics.prometheus import metrics

logger = structlog.get_logger(__name__)


class NotificationLevel(Enum):
    """Notification severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class NotificationEvent:
    """Represents a notification event."""

    level: NotificationLevel
    title: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "metadata": self.metadata or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class NotificationConfig:
    """Configuration for notifications."""

    slack_webhook_url: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: Optional[int] = None
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: Optional[List[str]] = None
    min_level: NotificationLevel = NotificationLevel.ERROR

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        """Create config from environment variables."""
        return cls(
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            email_smtp_host=os.getenv("EMAIL_SMTP_HOST"),
            email_smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "0")) or None,
            email_username=os.getenv("EMAIL_USERNAME"),
            email_password=os.getenv("EMAIL_PASSWORD"),
            email_recipients=os.getenv("EMAIL_RECIPIENTS", "").split(",")
            if os.getenv("EMAIL_RECIPIENTS")
            else None,
            min_level=NotificationLevel(os.getenv("MIN_NOTIFICATION_LEVEL", "error").lower()),
        )


class Notifier:
    """Handles sending notifications through various channels."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize the notifier.

        Args:
            config: Optional notification configuration
        """
        self.config = config or NotificationConfig.from_env()
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize notification metrics."""
        metrics.register_counter(
            "notifications_sent_total",
            "Total number of notifications sent",
            ["level", "channel"],
        )
        metrics.register_counter(
            "notification_errors_total",
            "Total number of notification errors",
            ["channel"],
        )

    async def notify(self, event: NotificationEvent) -> None:
        """Send a notification through configured channels.

        Args:
            event: Notification event to send
        """
        if event.level.value < self.config.min_level.value:
            return

        if not event.timestamp:
            event.timestamp = datetime.utcnow()

        tasks = []
        if self.config.slack_webhook_url:
            tasks.append(self._send_slack_notification(event))
        if all(
            [
                self.config.email_smtp_host,
                self.config.email_smtp_port,
                self.config.email_recipients,
            ]
        ):
            tasks.append(self._send_email_notification(event))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_slack_notification(self, event: NotificationEvent) -> None:
        """Send notification to Slack.

        Args:
            event: Notification event to send
        """
        try:
            message = {
                "text": f"*{event.title}*\n{event.message}",
                "attachments": [
                    {
                        "color": self._get_slack_color(event.level),
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in (event.metadata or {}).items()
                        ],
                        "ts": event.timestamp.timestamp()
                        if event.timestamp
                        else datetime.utcnow().timestamp(),
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.slack_webhook_url,
                    json=message,
                ) as response:
                    if response.status == 200:
                        metrics.increment_counter(
                            "notifications_sent_total",
                            {"level": event.level.value, "channel": "slack"},
                        )
                    else:
                        logger.error(
                            "slack_notification_error",
                            status=response.status,
                            response=await response.text(),
                        )
                        metrics.increment_counter(
                            "notification_errors_total",
                            {"channel": "slack"},
                        )

        except Exception as e:
            logger.error("slack_notification_error", error=str(e))
            metrics.increment_counter(
                "notification_errors_total",
                {"channel": "slack"},
            )

    def _get_slack_color(self, level: NotificationLevel) -> str:
        """Get Slack color for notification level.

        Args:
            level: Notification level

        Returns:
            Slack color code
        """
        return {
            NotificationLevel.INFO: "#36a64f",  # green
            NotificationLevel.WARNING: "#ffa500",  # orange
            NotificationLevel.ERROR: "#ff0000",  # red
            NotificationLevel.CRITICAL: "#7b001c",  # dark red
        }.get(
            level, "#000000"
        )  # black for unknown levels

    async def _send_email_notification(self, event: NotificationEvent) -> None:
        """Send notification via email.

        Args:
            event: Notification event to send
        """
        # Email implementation would go here
        # For now, just log and increment metrics
        logger.info(
            "email_notification_skipped",
            message="Email notifications not implemented yet",
        )
        metrics.increment_counter(
            "notifications_sent_total",
            {"level": event.level.value, "channel": "email"},
        )
