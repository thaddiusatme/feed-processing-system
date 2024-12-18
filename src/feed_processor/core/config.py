"""
Configuration module for the feed processor.

This module provides configuration classes and utilities for managing feed processing
settings, including feed sources, processing intervals, and logging configuration.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

"""Unified configuration management for the feed processor."""


@dataclass
class AirtableConfig:
    """Configuration for Airtable connection."""

    api_key: str
    base_id: str
    table_id: str

    @classmethod
    def from_env(cls) -> "AirtableConfig":
        """Create AirtableConfig from environment variables."""
        required_vars = {
            "api_key": "AIRTABLE_API_KEY",
            "base_id": "AIRTABLE_BASE_ID",
            "table_id": "AIRTABLE_TABLE_ID",
        }

        missing = [env_var for var, env_var in required_vars.items() if not os.getenv(env_var)]

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            api_key=os.getenv("AIRTABLE_API_KEY"),
            base_id=os.getenv("AIRTABLE_BASE_ID"),
            table_id=os.getenv("AIRTABLE_TABLE_ID"),
        )


@dataclass
class FeedConfig:
    """Configuration for feed processing."""

    feeds: List[Dict]
    fetch_interval_seconds: int = 300
    max_items_per_fetch: int = 30
    retry_interval_seconds: int = 60
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "FeedConfig":
        """Load feed configuration from JSON file.

        Args:
            config_path: Optional path to config file. If not provided,
                       will look in default location.
        """
        if config_path is None:
            config_path = Path(__file__).parents[3] / "config" / "feed_config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")

        with open(config_path, "r") as f:
            config = json.load(f)

        return cls(
            feeds=config["feeds"],
            fetch_interval_seconds=config.get("fetch_interval_seconds", 300),
            max_items_per_fetch=config.get("max_items_per_fetch", 30),
            retry_interval_seconds=config.get("retry_interval_seconds", 60),
            log_level=config.get("log_level", "INFO"),
        )


# Airtable field mappings
FIELD_MAPPINGS: Dict[str, str] = {
    "title": "Title",
    "url": "Link",
    "description": "Description",
    "published_at": "PublishDate",
    "status": "Status",
    "topics": "Topics",
    "tags": "Tags",
    "content_type": "Content Type",
    "feed_id": "FeedID",
    "author": "Author",
}

# Default values for certain fields
DEFAULT_VALUES = {"status": "New", "content_type": "BLOG", "tags": [], "topics": []}
