"""
Integration tests for Airtable client.
"""
import os
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv

from feed_processor.storage.airtable_client import AirtableClient, AirtableConfig
from feed_processor.storage.models import ContentItem, ContentStatus, ContentType

# Load environment variables
load_dotenv()


@pytest.fixture
def airtable_config():
    """Create Airtable configuration from environment variables."""
    return AirtableConfig(
        api_key=os.getenv("AIRTABLE_API_KEY"),
        base_id=os.getenv("AIRTABLE_BASE_ID"),
        table_id=os.getenv("AIRTABLE_TABLE_ID"),
        rate_limit_per_sec=float(os.getenv("AIRTABLE_RATE_LIMIT", "0.2")),
        batch_size=int(os.getenv("AIRTABLE_BATCH_SIZE", "10")),
    )


@pytest.fixture
def airtable_client(airtable_config):
    """Create Airtable client instance."""
    return AirtableClient(airtable_config)


@pytest.fixture
def test_content_item():
    """Create a test content item."""
    return ContentItem(
        title="Test Article",
        content="This is a test article content.",
        url="https://example.com/test-article",
        content_type=ContentType.BLOG,
        published_at=datetime.now(timezone.utc),
        source_id="test_source_001",
    )


@pytest.mark.asyncio
async def test_create_and_get_record(airtable_client, test_content_item):
    """Test creating and retrieving a record."""
    # Create record
    record = test_content_item.to_airtable_record()
    record_ids = await airtable_client.create_records([record])
    assert len(record_ids) == 1, "Should create one record"

    # Get record
    retrieved_record = await airtable_client.get_record(record_ids[0])
    assert retrieved_record is not None, "Should retrieve the created record"

    # Verify fields
    fields = retrieved_record["fields"]
    assert fields["Title"] == test_content_item.title
    assert fields["Content"] == test_content_item.content
    assert fields["URL"] == str(test_content_item.url)
    assert fields["Content Type"] == test_content_item.content_type.value
    assert fields["Source ID"] == test_content_item.source_id
