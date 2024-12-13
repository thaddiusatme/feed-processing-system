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

class ValidationResult:
    """Result of feed validation."""
    def __init__(self, valid: bool, errors: Optional[List[str]] = None):
        self.valid = valid
        self.errors = errors or []

class FeedValidator:
    """Validates RSS/Atom feeds."""
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.required_fields = self.config.get('required_fields', [
            'title',
            'link',
            'description'
        ])
        self.max_title_length = self.config.get('max_title_length', 100)
        self.max_description_length = self.config.get('max_description_length', 5000)

    def validate(self, feed_url: str) -> ValidationResult:
        """Validate a feed URL."""
        errors = []

        # Validate URL format
        try:
            parsed_url = urlparse(feed_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                errors.append("Invalid feed URL format")
                return ValidationResult(valid=False, errors=errors)
        except Exception as e:
            errors.append(f"URL parsing error: {str(e)}")
            return ValidationResult(valid=False, errors=errors)

        # Fetch feed content
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()
            feed_content = response.text
        except requests.RequestException as e:
            errors.append(f"Failed to fetch feed: {str(e)}")
            return ValidationResult(valid=False, errors=errors)

        # Parse feed
        feed = feedparser.parse(feed_content)
        if feed.bozo:
            errors.append(f"Feed parsing error: {str(feed.bozo_exception)}")
            return ValidationResult(valid=False, errors=errors)

        # Validate required fields
        for field in self.required_fields:
            if not feed.feed.get(field):
                errors.append(f"Missing required field: {field}")

        # Validate feed entries
        if not feed.entries:
            errors.append("Feed contains no entries")
        else:
            for entry in feed.entries:
                # Validate entry fields
                if not entry.get('title'):
                    errors.append("Entry missing title")
                elif len(entry.title) > self.max_title_length:
                    errors.append(f"Entry title exceeds maximum length of {self.max_title_length} characters")

                if not entry.get('description'):
                    errors.append("Entry missing description")
                elif len(entry.description) > self.max_description_length:
                    errors.append(f"Entry description exceeds maximum length of {self.max_description_length} characters")

                # Validate dates
                if entry.get('published'):
                    try:
                        published = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
                        if published > datetime.utcnow():
                            errors.append("Entry has future publication date")
                    except ValueError:
                        errors.append("Invalid publication date format")

        return ValidationResult(valid=len(errors) == 0, errors=errors)
