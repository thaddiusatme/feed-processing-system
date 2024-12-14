"""Feed content validation."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from xml.etree import ElementTree as ET

import structlog
from dateutil.parser import parse as parse_date

logger = structlog.get_logger(__name__)


@dataclass
class FeedValidationResult:
    """Result of feed validation."""

    is_valid: bool
    feed_type: Optional[str]
    parsed_feed: Optional[Dict[str, Any]]
    error_message: Optional[str] = None


class FeedValidator:
    """Validator for different feed formats (RSS, Atom, JSON)."""

    @staticmethod
    def validate_feed(feed_content: str) -> FeedValidationResult:
        """Validate and parse a feed string.

        Args:
            feed_content: String containing the feed content

        Returns:
            FeedValidationResult containing validation status and parsed feed
        """
        try:
            # Try parsing as JSON first
            try:
                data = json.loads(feed_content)
                if "version" in data and "jsonfeed" in data["version"].lower():
                    parsed = {
                        "title": data.get("title"),
                        "link": data.get("home_page_url"),
                        "updated": parse_date(data["items"][0]["date_published"])
                        if data.get("items")
                        else None,
                        "entries": [
                            {
                                "title": item.get("title"),
                                "link": item.get("url"),
                                "summary": item.get("content_text"),
                                "updated": parse_date(item["date_published"])
                                if "date_published" in item
                                else None,
                            }
                            for item in data.get("items", [])
                        ],
                    }
                    return FeedValidationResult(True, "json", parsed)
            except json.JSONDecodeError:
                pass

            # Try parsing as XML (RSS or Atom)
            root = ET.fromstring(feed_content)

            # Check for Atom feed
            if root.tag.endswith("feed"):
                parsed = {
                    "title": root.find(".//{http://www.w3.org/2005/Atom}title").text,
                    "link": root.find(".//{http://www.w3.org/2005/Atom}link").get("href"),
                    "updated": parse_date(
                        root.find(".//{http://www.w3.org/2005/Atom}updated").text
                    ),
                    "entries": [
                        {
                            "title": entry.find("{http://www.w3.org/2005/Atom}title").text,
                            "link": entry.find("{http://www.w3.org/2005/Atom}link").get("href"),
                            "summary": entry.find("{http://www.w3.org/2005/Atom}summary").text
                            if entry.find("{http://www.w3.org/2005/Atom}summary") is not None
                            else None,
                            "updated": parse_date(
                                entry.find("{http://www.w3.org/2005/Atom}updated").text
                            ),
                        }
                        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry")
                    ],
                }
                return FeedValidationResult(True, "atom", parsed)

            # Check for RSS feed
            if root.tag == "rss":
                channel = root.find("channel")
                if channel is None:
                    return FeedValidationResult(
                        False, "rss", None, "Missing required channel element"
                    )

                required_fields = ["title", "link"]
                missing_fields = [field for field in required_fields if channel.find(field) is None]
                if missing_fields:
                    return FeedValidationResult(
                        False, "rss", None, f"Missing required fields: {', '.join(missing_fields)}"
                    )

                parsed = {
                    "title": channel.find("title").text,
                    "link": channel.find("link").text,
                    "updated": parse_date(channel.find("pubDate").text)
                    if channel.find("pubDate") is not None
                    else None,
                    "entries": [
                        {
                            "title": item.find("title").text,
                            "link": item.find("link").text,
                            "summary": item.find("description").text
                            if item.find("description") is not None
                            else None,
                            "updated": parse_date(item.find("pubDate").text)
                            if item.find("pubDate") is not None
                            else None,
                        }
                        for item in channel.findall("item")
                    ],
                }
                return FeedValidationResult(True, "rss", parsed)

            return FeedValidationResult(False, None, None, "Unknown feed format")

        except Exception as e:
            return FeedValidationResult(False, None, None, str(e))
