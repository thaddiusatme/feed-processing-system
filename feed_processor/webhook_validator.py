"""
Webhook data validation for feed processing system.
"""
from datetime import datetime
from typing import Any, Dict

import structlog
from dateutil.parser import parse as parse_date

from .exceptions import ValidationError
from .models import FeedData, SourceMetadata

logger = structlog.get_logger(__name__)


def validate_feed_data(data: Dict[str, Any]) -> FeedData:
    """
    Validate incoming webhook data against our schema.

    Args:
        data: Dictionary containing the webhook payload

    Returns:
        FeedData: Validated and parsed feed data

    Raises:
        ValidationError: If data fails validation
    """
    try:
        # Validate required fields
        required_fields = ["title", "contentType", "brief", "priority", "sourceMetadata"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")

        # Validate source metadata
        source_meta = data["sourceMetadata"]
        required_meta_fields = ["feedId", "originalUrl", "publishDate"]
        missing_meta = [field for field in required_meta_fields if field not in source_meta]
        if missing_meta:
            raise ValidationError(f"Missing required metadata fields: {', '.join(missing_meta)}")

        # Parse and validate dates
        try:
            publish_date = parse_date(source_meta["publishDate"])
        except ValueError as e:
            raise ValidationError(f"Invalid publish date format: {str(e)}")

        # Create SourceMetadata object
        metadata = SourceMetadata(
            feed_id=source_meta["feedId"],
            original_url=source_meta["originalUrl"],
            publish_date=publish_date,
            author=source_meta.get("author"),
            tags=source_meta.get("tags", []),
        )

        # Create and return FeedData object
        # This will perform additional validation in __post_init__
        return FeedData(
            title=data["title"],
            content_type=data["contentType"],
            brief=data["brief"],
            priority=data["priority"],
            source_metadata=metadata,
            research_status=data.get("research_status"),
            quality_score=data.get("quality_score"),
        )

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Error validating feed data: {str(e)}")
