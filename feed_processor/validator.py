"""Feed validator module with enhanced validation features and performance optimizations."""

import asyncio
import concurrent.futures
import functools
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parsedate_tz
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiohttp
import chardet
import feedparser
from cachetools import TTLCache

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Represents the result of a feed validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Union[int, float]]
    encoding: str
    format: str = "rss"  # or atom
    validation_time: float = 0.0
    error_type: str = "none"  # Can be: none, critical, validation, format

    def to_dict(self) -> dict:
        """Convert the validation result to a dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert the validation result to JSON."""
        return json.dumps(self.to_dict(), indent=2)


class FeedValidator:
    """Enhanced feed validator with caching and parallel validation support."""

    def __init__(self, strict_mode: bool = False, use_cache: bool = False, cache_ttl: int = 3600):
        """Initialize the feed validator."""
        self.strict_mode = strict_mode
        self.use_cache = use_cache
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        self.cache_ttl = cache_ttl

    def _get_from_cache(self, cache_key: str) -> Optional[ValidationResult]:
        """Get cached validation result if available."""
        if not self.use_cache:
            return None
        return self.cache.get(cache_key)

    def _add_to_cache(self, cache_key: str, result: ValidationResult) -> None:
        """Cache validation result."""
        if not self.use_cache:
            return
        self.cache[cache_key] = result

    async def __aenter__(self):
        """Set up async resources."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async resources."""
        if self.session:
            await self.session.close()

    async def validate(self, feed_path: str) -> ValidationResult:
        """Validate a feed file."""
        start_time = datetime.now()
        errors = []
        warnings = []
        stats = {}
        encoding = None
        error_type = "none"

        try:
            # Check cache first
            if self.use_cache:
                cache_key = f"{feed_path}_{self.strict_mode}"
                cached_result = self._get_from_cache(cache_key)
                if cached_result:
                    return cached_result

            # Check if file exists and is readable
            if not os.path.isfile(feed_path):
                errors.append(f"Feed file '{feed_path}' does not exist")
                error_type = "critical"
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    stats=stats,
                    encoding=encoding,
                    validation_time=(datetime.now() - start_time).total_seconds(),
                    error_type=error_type,
                )

            # Check file size
            file_size = os.path.getsize(feed_path)
            if file_size == 0:
                errors.append(f"Feed file '{feed_path}' is empty")
                error_type = "critical"
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    stats=stats,
                    encoding=encoding,
                    validation_time=(datetime.now() - start_time).total_seconds(),
                    error_type=error_type,
                )

            # Detect encoding and parse feed
            with open(feed_path, "rb") as f:
                raw_content = f.read()
                try:
                    encoding = chardet.detect(raw_content)["encoding"] or "utf-8"
                    content = raw_content.decode(encoding)
                except UnicodeDecodeError as e:
                    errors.append(
                        f"Invalid encoding: {encoding} for file '{feed_path}'. Error: {str(e)}"
                    )
                    error_type = "critical"
                    return ValidationResult(
                        is_valid=False,
                        errors=errors,
                        warnings=warnings,
                        stats=stats,
                        encoding=encoding,
                        validation_time=(datetime.now() - start_time).total_seconds(),
                        error_type=error_type,
                    )

            # Parse feed
            feed = feedparser.parse(content)

            # Check for basic parsing errors
            if feed.bozo:
                errors.append(
                    f"Feed parsing error: {str(feed.bozo_exception)} for file '{feed_path}'"
                )
                error_type = "critical"
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    stats=stats,
                    encoding=encoding,
                    validation_time=(datetime.now() - start_time).total_seconds(),
                    error_type=error_type,
                )

            # Validate feed structure
            if not feed.feed:
                errors.append(
                    f"Invalid feed structure: missing channel information for file '{feed_path}'"
                )
                error_type = "critical"
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    stats=stats,
                    encoding=encoding,
                    validation_time=(datetime.now() - start_time).total_seconds(),
                    error_type=error_type,
                )

            # Required channel elements
            missing_required = False
            if not feed.feed.get("title"):
                errors.append(f"Missing required element: channel title for file '{feed_path}'")
                missing_required = True
            if not feed.feed.get("link"):
                errors.append(f"Missing required element: channel link for file '{feed_path}'")
                missing_required = True
            if not feed.feed.get("description"):
                errors.append(
                    f"Missing required element: channel description for file '{feed_path}'"
                )
                missing_required = True

            # Validate dates
            has_format_error = False
            if feed.feed.get("pubDate"):
                try:
                    feedparser._parse_date(feed.feed.pubDate)
                except (ValueError, AttributeError, TypeError) as e:
                    errors.append(
                        f"Invalid publication date in channel for file '{feed_path}'. Error: {str(e)}"
                    )
                    has_format_error = True

            # Validate URLs
            if feed.feed.get("link") and not feed.feed["link"].startswith(("http://", "https://")):
                errors.append(f"Invalid URL format in channel link for file '{feed_path}'")
                has_format_error = True

            # Validate feed items
            if not feed.entries:
                errors.append(f"No feed items found for file '{feed_path}'")
                error_type = "critical"
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    stats=stats,
                    encoding=encoding,
                    validation_time=(datetime.now() - start_time).total_seconds(),
                    error_type=error_type,
                )

            for item in feed.entries:
                # Required elements
                if not item.get("title"):
                    errors.append(f"Missing required element: item title for file '{feed_path}'")
                    missing_required = True
                if not item.get("link"):
                    errors.append(f"Missing required element: item link for file '{feed_path}'")
                    missing_required = True

                # Validate dates
                if item.get("pubDate"):
                    try:
                        feedparser._parse_date(item.pubDate)
                    except (ValueError, AttributeError, TypeError) as e:
                        errors.append(
                            f"Invalid publication date in item for file '{feed_path}'. Error: {str(e)}"
                        )
                        has_format_error = True

                # Validate URLs
                if item.get("link") and not item["link"].startswith(("http://", "https://")):
                    errors.append(f"Invalid URL format in item link for file '{feed_path}'")
                    has_format_error = True

                # Validate GUID length
                if item.get("guid") and len(item["guid"]) > 512:
                    errors.append(
                        f"GUID exceeds maximum length of 512 characters for file '{feed_path}'"
                    )
                    has_format_error = True

                # Validate image URLs
                if item.get("image"):
                    if not isinstance(item["image"], str) or not item["image"].startswith(
                        ("http://", "https://")
                    ):
                        errors.append(f"Invalid image URL format for file '{feed_path}'")
                        has_format_error = True

            # Additional checks in strict mode
            if self.strict_mode:
                # Check content length
                if feed.feed.get("description") and len(feed.feed["description"]) > 4000:
                    errors.append(
                        f"Channel description exceeds maximum length for file '{feed_path}'"
                    )
                    missing_required = True

                for item in feed.entries:
                    if item.get("description") and len(item["description"]) > 4000:
                        errors.append(
                            f"Item description exceeds maximum length for file '{feed_path}'"
                        )
                        missing_required = True

            # Collect statistics
            stats = {
                "item_count": len(feed.entries),
                "has_images": any(item.get("image") for item in feed.entries),
                "has_categories": any(item.get("tags") for item in feed.entries),
            }

            # Set error type based on the types of errors found
            if len(errors) > 0:
                if error_type == "none":  # If no critical errors were found
                    if self.strict_mode:
                        error_type = "critical"  # All errors are critical in strict mode
                    elif missing_required:
                        error_type = "validation"
                    elif has_format_error:
                        error_type = "validation"  # Format errors are treated as validation errors
                    else:
                        error_type = "validation"  # Default to validation for any other errors

            # Cache the result if caching is enabled
            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                stats=stats,
                encoding=encoding,
                validation_time=(datetime.now() - start_time).total_seconds(),
                error_type=error_type,
            )

            if self.use_cache:
                self._add_to_cache(cache_key, result)

            return result

        except Exception as e:
            errors.append(f"Validation error: {str(e)} for file '{feed_path}'")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                stats=stats,
                encoding=encoding,
                validation_time=(datetime.now() - start_time).total_seconds(),
                error_type="critical",
            )
