"""Example of custom priority rules implementation."""
from typing import Dict, Any, List, Set
from datetime import datetime, timezone
from feed_processor import FeedProcessor, Priority

class CustomFeedProcessor(FeedProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.breaking_keywords: Set[str] = set(
            self.config.get("BREAKING_NEWS_KEYWORDS", "").split(",")
        )
        self.trusted_sources: Set[str] = set(
            self.config.get("TRUSTED_SOURCES", "").split(",")
        )
        self.high_priority_categories: Set[str] = set(
            self.config.get("HIGH_PRIORITY_CATEGORIES", "").split(",")
        )

    def _is_breaking_news(self, item: Dict[str, Any]) -> bool:
        """Check if the item is breaking news based on keywords."""
        title = item.get("title", "").lower()
        return any(keyword in title for keyword in self.breaking_keywords)

    def _is_from_trusted_source(self, item: Dict[str, Any]) -> bool:
        """Check if the item is from a trusted source."""
        source = item.get("source", {}).get("name", "").lower()
        return source in self.trusted_sources

    def _is_recent(self, item: Dict[str, Any], hours: int = 1) -> bool:
        """Check if the item is recent within specified hours."""
        published = datetime.fromisoformat(item.get("published", ""))
        age = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        return age <= hours

    def _get_category_priority(self, item: Dict[str, Any]) -> Priority:
        """Determine priority based on item category."""
        categories = set(item.get("categories", []))
        if categories & self.high_priority_categories:
            return Priority.HIGH
        return Priority.NORMAL

    def _determine_priority(self, item: Dict[str, Any]) -> Priority:
        """Custom priority determination logic."""
        # Breaking news gets highest priority
        if self._is_breaking_news(item):
            return Priority.HIGH

        # Recent items from trusted sources get high priority
        if self._is_from_trusted_source(item) and self._is_recent(item):
            return Priority.HIGH

        # Use category-based priority
        category_priority = self._get_category_priority(item)
        if category_priority == Priority.HIGH:
            return Priority.HIGH

        # Default to normal priority for recent items, low for older ones
        return Priority.NORMAL if self._is_recent(item, hours=24) else Priority.LOW
