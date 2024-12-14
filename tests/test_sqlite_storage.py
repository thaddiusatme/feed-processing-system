"""Tests for SQLite storage implementation."""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from feed_processor.storage.models import ContentItem, ContentStatus, ContentType
from feed_processor.storage.sqlite_storage import SQLiteConfig, SQLiteStorage


@pytest.fixture
def test_db_path(tmp_path):
    """Fixture providing a temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def storage(test_db_path):
    """Fixture providing a SQLiteStorage instance."""
    config = SQLiteConfig(db_path=test_db_path)
    storage = SQLiteStorage(config)
    yield storage


@pytest.fixture
def sample_item():
    """Fixture providing a sample content item."""
    return ContentItem(
        title="Test Item",
        content="Test content",
        url="https://example.com/test",
        content_type=ContentType.BLOG,
        published_at=datetime.now(timezone.utc),
        source_id="test_source",
        status=ContentStatus.PENDING,
        author="Test Author",
    )


def test_storage_initialization(test_db_path):
    """Test storage initialization creates database and tables."""
    config = SQLiteConfig(db_path=test_db_path)
    storage = SQLiteStorage(config)

    assert Path(test_db_path).exists()

    # Check tables exist
    with storage._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "feed_items" in tables
        assert "error_log" in tables


def test_store_item(storage, sample_item):
    """Test storing a content item."""
    assert storage.store_item(sample_item)

    # Verify item was stored
    with storage._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feed_items")
        row = cursor.fetchone()

        assert row["title"] == sample_item.title
        assert row["content_type"] == sample_item.content_type.value
        assert row["brief"] == sample_item.content
        assert row["feed_id"] == sample_item.source_id
        assert row["original_url"] == sample_item.url
        assert row["author"] == sample_item.author


def test_duplicate_detection(storage, sample_item):
    """Test duplicate URL detection."""
    assert storage.store_item(sample_item)
    assert storage.is_duplicate(sample_item.url)
    assert not storage.is_duplicate("https://example.com/other")


def test_error_logging(storage):
    """Test error logging functionality."""
    storage.log_error("test_error", "Test error message")

    with storage._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM error_log")
        row = cursor.fetchone()

        assert row["error_type"] == "test_error"
        assert row["error_message"] == "Test error message"


def test_get_items_by_status(storage, sample_item):
    """Test retrieving items by status."""
    storage.store_item(sample_item)

    items = storage.get_items_by_status(ContentStatus.PENDING)
    assert len(items) == 1
    assert items[0].title == sample_item.title

    items = storage.get_items_by_status(ContentStatus.PROCESSED)
    assert len(items) == 0


def test_get_items_by_status_with_limit(storage, sample_item):
    """Test retrieving items with limit."""
    # Store multiple items
    for i in range(3):
        item = sample_item.copy()
        item.url = f"https://example.com/test{i}"
        storage.store_item(item)

    items = storage.get_items_by_status(ContentStatus.PENDING, limit=2)
    assert len(items) == 2


def test_store_item_with_long_content(storage, sample_item):
    """Test storing item with content exceeding max length."""
    sample_item.content = "x" * 3000  # Exceeds 2000 char limit
    assert storage.store_item(sample_item)

    items = storage.get_items_by_status(ContentStatus.PENDING)
    assert len(items[0].content) == 2000  # Verify content was truncated
