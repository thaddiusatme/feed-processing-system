"""
Data models for feed processing system.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class SourceMetadata:
    feed_id: str
    original_url: str
    publish_date: datetime
    author: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class FeedData:
    title: str
    content_type: str
    brief: str
    priority: str
    source_metadata: SourceMetadata
    research_status: Optional[str] = None
    quality_score: Optional[float] = None

    def __post_init__(self):
        # Validate content type
        valid_content_types = {"BLOG", "VIDEO", "SOCIAL"}
        if self.content_type not in valid_content_types:
            raise ValueError(f"Invalid content type. Must be one of: {valid_content_types}")

        # Validate priority
        valid_priorities = {"High", "Medium", "Low"}
        if self.priority not in valid_priorities:
            raise ValueError(f"Invalid priority. Must be one of: {valid_priorities}")

        # Validate string lengths
        if len(self.title) > 255:
            raise ValueError("Title must not exceed 255 characters")
        if len(self.brief) > 2000:
            raise ValueError("Brief must not exceed 2000 characters")

        # Initialize optional fields
        if self.quality_score is None:
            self.quality_score = 0.0
