from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import feedparser
import json
import re
from urllib.parse import urlparse


@dataclass
class FeedValidationResult:
    is_valid: bool
    feed_type: Optional[str] = None
    error_message: Optional[str] = None
    parsed_feed: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = None
    validation_warnings: List[str] = None


class FeedValidator:
    REQUIRED_FIELDS = {
        "rss": ["title", "link", "description"],
        "atom": ["title", "id", "updated"],
        "json": ["version", "title", "items"],
    }

    CONTENT_TYPES = ["BLOG", "VIDEO", "SOCIAL"]
    PRIORITY_LEVELS = ["High", "Medium", "Low"]

    @staticmethod
    def validate_feed(content: str) -> FeedValidationResult:
        """Validate and parse a feed string."""
        errors = []
        warnings = []

        # Try parsing as RSS/Atom first
        parsed = feedparser.parse(content)
        if parsed.get("version"):
            feed_type = "atom" if parsed.get("version").startswith("atom") else "rss"
            if FeedValidator._validate_required_fields(
                parsed.feed, FeedValidator.REQUIRED_FIELDS[feed_type]
            ):
                # Validate additional fields
                FeedValidator._validate_title(parsed.feed.get("title"), errors)
                FeedValidator._validate_url(parsed.feed.get("link"), errors)

                if not errors:
                    return FeedValidationResult(
                        is_valid=True,
                        feed_type=feed_type,
                        parsed_feed=FeedValidator._normalize_feed(parsed.feed, feed_type),
                        validation_errors=errors,
                        validation_warnings=warnings,
                    )
            else:
                errors.append(f"Missing required fields for {feed_type} feed")

            return FeedValidationResult(
                is_valid=False,
                feed_type=feed_type,
                error_message="Validation failed",
                validation_errors=errors,
                validation_warnings=warnings,
            )

        # Try parsing as JSON Feed
        try:
            json_feed = json.loads(content)
            if json_feed.get("version", "").startswith("https://jsonfeed.org/version/"):
                if FeedValidator._validate_required_fields(
                    json_feed, FeedValidator.REQUIRED_FIELDS["json"]
                ):
                    # Validate additional fields
                    FeedValidator._validate_title(json_feed.get("title"), errors)
                    FeedValidator._validate_url(json_feed.get("home_page_url"), errors)

                    if not errors:
                        return FeedValidationResult(
                            is_valid=True,
                            feed_type="json",
                            parsed_feed=FeedValidator._normalize_feed(json_feed, "json"),
                            validation_errors=errors,
                            validation_warnings=warnings,
                        )
                else:
                    errors.append("Missing required fields for JSON feed")

                return FeedValidationResult(
                    is_valid=False,
                    feed_type="json",
                    error_message="Validation failed",
                    validation_errors=errors,
                    validation_warnings=warnings,
                )
        except json.JSONDecodeError:
            pass

        return FeedValidationResult(
            is_valid=False,
            error_message="Unsupported or invalid feed format",
            validation_errors=errors,
            validation_warnings=warnings,
        )

    @staticmethod
    def _validate_required_fields(feed_data: Dict[str, Any], required_fields: list) -> bool:
        """Check if all required fields are present in the feed."""
        return all(field in feed_data for field in required_fields)

    @staticmethod
    def _validate_title(title: str, errors: List[str]) -> None:
        """Validate title according to schema rules."""
        if not title:
            errors.append("Title is required")
        elif len(title) > 255:
            errors.append("Title exceeds maximum length of 255 characters")
        elif re.search(r"<[^>]+>", title):
            errors.append("Title contains HTML tags")

    @staticmethod
    def _validate_url(url: str, errors: List[str]) -> None:
        """Validate URL according to schema rules."""
        if not url:
            errors.append("URL is required")
        elif len(url) > 2048:
            errors.append("URL exceeds maximum length of 2048 characters")
        else:
            try:
                result = urlparse(url)
                if not all([result.scheme, result.netloc]):
                    errors.append("Invalid URL format")
            except Exception:
                errors.append("Invalid URL format")

    @staticmethod
    def _validate_content_type(content_type: str, errors: List[str]) -> None:
        """Validate content type according to schema rules."""
        if content_type and content_type not in FeedValidator.CONTENT_TYPES:
            errors.append(
                f"Invalid content type. Must be one of: {', '.join(FeedValidator.CONTENT_TYPES)}"
            )

    @staticmethod
    def _validate_priority(priority: str, errors: List[str]) -> None:
        """Validate priority according to schema rules."""
        if priority and priority not in FeedValidator.PRIORITY_LEVELS:
            errors.append(
                f"Invalid priority. Must be one of: {', '.join(FeedValidator.PRIORITY_LEVELS)}"
            )

    @staticmethod
    def _validate_tags(tags: List[str], errors: List[str]) -> None:
        """Validate tags according to schema rules."""
        if tags:
            if len(tags) > 10:
                errors.append("Maximum of 10 tags allowed")
            for tag in tags:
                if len(tag) > 50:
                    errors.append(f"Tag '{tag}' exceeds maximum length of 50 characters")

    @staticmethod
    def _normalize_feed(feed_data: Dict[str, Any], feed_type: str) -> Dict[str, Any]:
        """Normalize feed data to match schema format."""
        normalized = {
            "id": feed_data.get("id") or feed_data.get("guid"),
            "title": feed_data.get("title"),
            "content": {
                "full": feed_data.get("content", ""),
                "brief": feed_data.get("summary", "")[:2000] if feed_data.get("summary") else "",
                "format": "html" if feed_type in ["rss", "atom"] else "text",
            },
            "metadata": {
                "source": {
                    "feedId": feed_data.get("feed_id", ""),
                    "url": feed_data.get("link") or feed_data.get("id"),
                    "publishDate": None,
                    "author": feed_data.get("author", ""),
                    "language": feed_data.get("language", ""),
                    "tags": feed_data.get("tags", []),
                },
                "processing": {
                    "receivedAt": datetime.now().isoformat(),
                    "processedAt": None,
                    "attempts": 0,
                    "status": "pending",
                },
            },
            "analysis": {
                "contentType": None,
                "priority": "Medium",  # Default priority
                "readabilityScore": None,
                "sentimentScore": None,
                "categories": [],
                "keywords": [],
            },
        }

        # Parse and normalize dates
        if feed_type == "atom":
            publish_date = feed_data.get("updated")
        elif feed_type == "rss":
            publish_date = feed_data.get("pubDate")
        else:  # json
            publish_date = feed_data.get("date_published")

        if publish_date:
            try:
                if isinstance(publish_date, str):
                    normalized["metadata"]["source"]["publishDate"] = datetime.fromisoformat(
                        publish_date.replace("Z", "+00:00")
                    ).isoformat()
                else:
                    normalized["metadata"]["source"]["publishDate"] = datetime(
                        *publish_date[:6]
                    ).isoformat()
            except (ValueError, TypeError):
                pass

        return normalized
