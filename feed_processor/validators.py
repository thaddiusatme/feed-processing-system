from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import feedparser
import json

@dataclass
class FeedValidationResult:
    is_valid: bool
    feed_type: Optional[str] = None
    error_message: Optional[str] = None
    parsed_feed: Optional[Dict[str, Any]] = None

class FeedValidator:
    REQUIRED_FIELDS = {
        'rss': ['title', 'link', 'description'],
        'atom': ['title', 'id', 'updated'],
        'json': ['version', 'title', 'items']
    }

    @staticmethod
    def validate_feed(content: str) -> FeedValidationResult:
        """Validate and parse a feed string."""
        # Try parsing as RSS/Atom first
        parsed = feedparser.parse(content)
        if parsed.get('version'):
            feed_type = 'atom' if parsed.get('version').startswith('atom') else 'rss'
            if FeedValidator._validate_required_fields(parsed.feed, FeedValidator.REQUIRED_FIELDS[feed_type]):
                return FeedValidationResult(
                    is_valid=True,
                    feed_type=feed_type,
                    parsed_feed=FeedValidator._normalize_feed(parsed.feed, feed_type)
                )
            return FeedValidationResult(
                is_valid=False,
                feed_type=feed_type,
                error_message=f"Missing required fields for {feed_type} feed"
            )

        # Try parsing as JSON Feed
        try:
            json_feed = json.loads(content)
            if json_feed.get('version', '').startswith('https://jsonfeed.org/version/'):
                if FeedValidator._validate_required_fields(json_feed, FeedValidator.REQUIRED_FIELDS['json']):
                    return FeedValidationResult(
                        is_valid=True,
                        feed_type='json',
                        parsed_feed=FeedValidator._normalize_feed(json_feed, 'json')
                    )
                return FeedValidationResult(
                    is_valid=False,
                    feed_type='json',
                    error_message="Missing required fields for JSON feed"
                )
        except json.JSONDecodeError:
            pass

        return FeedValidationResult(
            is_valid=False,
            error_message="Unsupported or invalid feed format"
        )

    @staticmethod
    def _validate_required_fields(feed_data: Dict[str, Any], required_fields: list) -> bool:
        """Check if all required fields are present in the feed."""
        return all(field in feed_data for field in required_fields)

    @staticmethod
    def _normalize_feed(feed_data: Dict[str, Any], feed_type: str) -> Dict[str, Any]:
        """Normalize feed data to a common format."""
        normalized = {
            'type': feed_type,
            'title': feed_data.get('title'),
            'link': feed_data.get('link') or feed_data.get('id'),
            'updated': None,
            'items': []
        }

        # Parse and normalize the updated date
        if feed_type == 'atom':
            updated = feed_data.get('updated')
            if updated:
                try:
                    normalized['updated'] = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
        elif feed_type == 'rss':
            updated = feed_data.get('published_parsed') or feed_data.get('updated_parsed')
            if updated:
                try:
                    normalized['updated'] = datetime(*updated[:6])
                except (ValueError, TypeError):
                    pass
        else:  # json
            updated = feed_data.get('date_modified')
            if updated:
                try:
                    normalized['updated'] = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

        return normalized
