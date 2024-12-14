"""Webhook configuration and delivery for feed processor."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from feed_processor.metrics.metrics import WEBHOOK_PAYLOAD_SIZE, WEBHOOK_RETRIES

logger = structlog.get_logger(__name__)


@dataclass
class WebhookConfig:
    """Configuration for webhook delivery."""

    url: str
    auth_token: Optional[str] = None
    batch_size: int = 10
    max_retries: int = 3
    timeout: float = 30.0

    def get_headers(self) -> Dict[str, str]:
        """Get headers for webhook request."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Feed-Processor/1.0",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers


async def deliver_webhook(
    config: WebhookConfig,
    payload: Dict[str, Any],
    session: Optional[aiohttp.ClientSession] = None,
) -> bool:
    """Deliver payload to webhook endpoint.

    Args:
        config: Webhook configuration
        payload: Data to send
        session: Optional aiohttp session to use

    Returns:
        bool: True if delivery was successful
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        # Track payload size
        payload_size = len(json.dumps(payload).encode("utf-8"))
        WEBHOOK_PAYLOAD_SIZE.observe(payload_size)

        retries = 0
        while retries <= config.max_retries:
            try:
                async with session.post(
                    config.url,
                    json=payload,
                    headers=config.get_headers(),
                    timeout=config.timeout,
                ) as response:
                    if response.status < 400:
                        return True
                    logger.error(
                        "Webhook delivery failed",
                        status=response.status,
                        url=config.url,
                        retry=retries,
                    )
            except Exception as e:
                logger.error(
                    "Webhook request failed",
                    error=str(e),
                    url=config.url,
                    retry=retries,
                )

            retries += 1
            WEBHOOK_RETRIES.inc()

        return False

    finally:
        if close_session:
            await session.close()


async def deliver_batch(
    config: WebhookConfig,
    items: List[Dict[str, Any]],
    session: Optional[aiohttp.ClientSession] = None,
) -> bool:
    """Deliver a batch of items to webhook endpoint.

    Args:
        config: Webhook configuration
        items: List of items to send
        session: Optional aiohttp session to use

    Returns:
        bool: True if all items were delivered successfully
    """
    if not items:
        return True

    # Split items into batches
    for i in range(0, len(items), config.batch_size):
        batch = items[i : i + config.batch_size]
        payload = {"items": batch}
        success = await deliver_webhook(config, payload, session)
        if not success:
            return False

    return True
