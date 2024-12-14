"""Data models for content storage."""

import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of content that can be stored."""

    BLOG = "BLOG"
    VIDEO = "VIDEO"
    SOCIAL = "SOCIAL"


class ContentStatus(str, Enum):
    """Status of content processing."""

    NEW = "new"
    PROCESSED = "processed"
    ERROR = "error"


class SourceMetadata(BaseModel):
    """Model for source metadata."""

    feedId: str
    originalUrl: HttpUrl
    publishDate: datetime
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ContentItem(BaseModel):
    """Model for content items."""

    title: str = Field(..., description="Content title")
    contentType: ContentType = Field(..., alias="content_type")
    brief: Optional[str] = Field(None, max_length=2000)
    sourceMetadata: SourceMetadata

    def to_db_record(self) -> dict:
        """Convert the model to database record format."""
        return {
            "title": self.title,
            "content_type": self.contentType.value,
            "brief": self.brief,
            "feed_id": self.sourceMetadata.feedId,
            "original_url": str(self.sourceMetadata.originalUrl),
            "publish_date": self.sourceMetadata.publishDate.isoformat(),
            "author": self.sourceMetadata.author,
            "processed_status": ContentStatus.NEW.value,
        }

    def to_airtable_record(self) -> dict:
        """Convert the model to Airtable record format."""
        # Strip HTML tags from description
        description = re.sub(r"<[^>]+>", "", self.brief) if self.brief else ""

        # Ensure date is in Airtable-compatible format (YYYY-MM-DD)
        try:
            # Convert to UTC timezone if not already
            if self.sourceMetadata.publishDate.tzinfo is None:
                publish_date = self.sourceMetadata.publishDate.replace(tzinfo=timezone.utc)
            else:
                publish_date = self.sourceMetadata.publishDate.astimezone(timezone.utc)

            # Format as YYYY-MM-DD which Airtable accepts
            publish_date = publish_date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Failed to format date: {e}")
            publish_date = None

        return {
            "fields": {
                "Title": self.title[:99] if self.title else "",  # Truncate if too long
                "Content Type": self.contentType.value,
                "Description": description[:500],  # Truncate if too long
                "FeedID": self.sourceMetadata.feedId,
                "Link": str(self.sourceMetadata.originalUrl),
                "PublishDate": publish_date,
                "Author": (self.sourceMetadata.author or "")[:99],  # Truncate if too long
            }
        }
