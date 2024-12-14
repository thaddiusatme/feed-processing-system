"""Tests for webhook validator."""
from datetime import datetime

import pytest

from feed_processor.exceptions import ValidationError
from feed_processor.models import FeedData, SourceMetadata
from feed_processor.webhook_validator import validate_feed_data


def test_validate_feed_data_success():
    """Test successful feed data validation."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
            "author": "Test Author",
            "tags": ["test"],
        },
    }

    result = validate_feed_data(test_data)

    assert isinstance(result, FeedData)
    assert result.title == "Test Feed"
    assert result.content_type == "BLOG"
    assert result.brief == "Test brief"
    assert result.priority == "High"
    assert isinstance(result.source_metadata, SourceMetadata)
    assert result.source_metadata.feed_id == "test123"
    assert result.source_metadata.author == "Test Author"
    assert result.source_metadata.tags == ["test"]


def test_validate_feed_data_missing_required_fields():
    """Test validation with missing required fields."""
    test_data = {
        "title": "Test Feed",
        # Missing contentType
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    with pytest.raises(ValidationError, match="Missing required fields: contentType"):
        validate_feed_data(test_data)


def test_validate_feed_data_missing_metadata_fields():
    """Test validation with missing metadata fields."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            # Missing originalUrl and publishDate
        },
    }

    with pytest.raises(ValidationError, match="Missing required metadata fields"):
        validate_feed_data(test_data)


def test_validate_feed_data_invalid_content_type():
    """Test validation with invalid content type."""
    test_data = {
        "title": "Test Feed",
        "contentType": "INVALID",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    with pytest.raises(ValidationError):
        validate_feed_data(test_data)


def test_validate_feed_data_invalid_priority():
    """Test validation with invalid priority."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "INVALID",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    with pytest.raises(ValidationError):
        validate_feed_data(test_data)


def test_validate_feed_data_invalid_date():
    """Test validation with invalid date format."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "invalid-date",
        },
    }

    with pytest.raises(ValidationError, match="Invalid publish date format"):
        validate_feed_data(test_data)


def test_validate_feed_data_title_too_long():
    """Test validation with title exceeding max length."""
    test_data = {
        "title": "T" * 256,  # 256 characters
        "contentType": "BLOG",
        "brief": "Test brief",
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    with pytest.raises(ValidationError):
        validate_feed_data(test_data)


def test_validate_feed_data_brief_too_long():
    """Test validation with brief exceeding max length."""
    test_data = {
        "title": "Test Feed",
        "contentType": "BLOG",
        "brief": "T" * 2001,  # 2001 characters
        "priority": "High",
        "sourceMetadata": {
            "feedId": "test123",
            "originalUrl": "http://test.com",
            "publishDate": "2024-12-13T18:44:27-08:00",
        },
    }

    with pytest.raises(ValidationError):
        validate_feed_data(test_data)
