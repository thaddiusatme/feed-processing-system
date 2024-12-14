import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

URL_PATTERN = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


@dataclass
class ContentItem:
    title: str
    content: str
    source_url: str
    published_date: datetime
    metadata: Dict[str, Any]

    def __post_init__(self):
        if not self.title:
            raise ValueError("Title cannot be empty")
        if not self.content:
            raise ValueError("Content cannot be empty")
        if not URL_PATTERN.match(self.source_url):
            raise ValueError("Invalid URL format")


@dataclass
class EnhancementResult:
    summary: str
    key_points: List[str]
    verified_facts: List[Dict[str, Any]]
    credibility_score: float
    quality_score: float
    processing_metadata: Dict[str, Any]

    def __post_init__(self):
        if not self.summary:
            raise ValueError("Summary cannot be empty")

        if not 0 <= self.credibility_score <= 1:
            raise ValueError("Credibility score must be between 0 and 1")

        if not 0 <= self.quality_score <= 1:
            raise ValueError("Quality score must be between 0 and 1")

        for fact in self.verified_facts:
            if "fact" not in fact or "confidence" not in fact:
                raise ValueError("Invalid fact format")
