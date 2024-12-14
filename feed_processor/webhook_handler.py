"""
Webhook handler for processing incoming feed data.
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Union

from .exceptions import RateLimitError, WebhookError
from .models import FeedData, SourceMetadata
from .storage import GoogleDriveStorage
from .validators import validate_feed_data

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles incoming webhook requests for feed processing."""

    def __init__(self, api_key: str, drive_storage: GoogleDriveStorage):
        self.api_key = api_key
        self.drive_storage = drive_storage
        self.last_request_time = 0
        self.rate_limit_delay = 0.2  # 200ms between requests

    def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            raise RateLimitError(
                f"Rate limit exceeded. Please wait {self.rate_limit_delay - time_since_last:.2f}s"
            )

        self.last_request_time = current_time

    def validate_auth(self, provided_key: str) -> bool:
        """Validate the API key."""
        return provided_key == self.api_key

    def process_webhook(self, data: Dict, auth_key: str) -> Dict:
        """Process incoming webhook data."""
        try:
            if not self.validate_auth(auth_key):
                raise WebhookError("Invalid API key")

            self._check_rate_limit()

            # Validate incoming data
            feed_data = validate_feed_data(data)

            # Create folder structure
            idea_id = feed_data.source_metadata.feed_id
            folder_structure = [
                f"{idea_id}/research",
                f"{idea_id}/drafts",
                f"{idea_id}/media",
                f"{idea_id}/reviews",
                f"{idea_id}/final",
                f"{idea_id}/archive",
            ]

            for folder in folder_structure:
                self.drive_storage.create_folder(folder)

            # Store initial metadata
            metadata = {
                "created_at": datetime.utcnow().isoformat(),
                "status": "New",
                "content_type": feed_data.content_type,
                "priority": feed_data.priority,
                "quality_score": feed_data.quality_score,
            }

            self.drive_storage.write_json(f"{idea_id}/metadata.json", metadata)

            return {
                "status": "success",
                "idea_id": idea_id,
                "message": "Feed data processed successfully",
            }

        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise WebhookError(f"Failed to process webhook: {str(e)}")
