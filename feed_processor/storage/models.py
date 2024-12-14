"""
Data models for content storage.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ContentType(str, Enum):
    """Types of content that can be stored."""

    BLOG = "BLOG"
    VIDEO = "VIDEO"
    SOCIAL = "SOCIAL"


class ContentStatus(str, Enum):
    """Status of content processing."""

    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    ERROR = "ERROR"


class ContentItem(BaseModel):
    """Model for content items to be stored in Airtable."""

    title: str = Field(..., max_length=255)
    content: str = Field(..., max_length=2000)
    url: HttpUrl
    content_type: ContentType
    published_at: datetime
    source_id: str = Field(..., description="Original source identifier")
    status: ContentStatus = Field(default=ContentStatus.PENDING)
    error_message: Optional[str] = None
    processing_attempts: int = Field(default=0)
    processed_at: Optional[datetime] = None

    def to_airtable_record(self) -> dict:
        """Convert the model to Airtable record format."""
        return {
            "fields": {
                "Title": self.title,
                "Content": self.content,
                "URL": str(self.url),
                "Content Type": self.content_type.value,
                "Published At": self.published_at.isoformat(),
                "Source ID": self.source_id,
                "Status": self.status.value,
                "Error Message": self.error_message,
                "Processing Attempts": self.processing_attempts,
                "Processed At": self.processed_at.isoformat() if self.processed_at else None,
            }
        }
