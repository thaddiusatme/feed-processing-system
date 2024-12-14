from datetime import datetime

import pytest

from feed_processor.content_enhancement.models import ContentItem, EnhancementResult


class TestContentItem:
    @pytest.fixture
    def valid_content_item(self):
        return ContentItem(
            title="Test Title",
            content="Test content body",
            source_url="https://example.com/article",
            published_date=datetime.utcnow(),
            metadata={"author": "John Doe", "category": "Technology"},
        )

    def test_content_item_creation(self, valid_content_item):
        """Test that ContentItem can be created with valid data"""
        assert valid_content_item.title == "Test Title"
        assert valid_content_item.content == "Test content body"
        assert valid_content_item.source_url == "https://example.com/article"
        assert isinstance(valid_content_item.published_date, datetime)
        assert valid_content_item.metadata["author"] == "John Doe"
        assert valid_content_item.metadata["category"] == "Technology"

    def test_content_item_invalid_url(self):
        """Test that ContentItem raises ValueError for invalid URLs"""
        with pytest.raises(ValueError, match="Invalid URL format"):
            ContentItem(
                title="Test",
                content="Test",
                source_url="invalid-url",
                published_date=datetime.utcnow(),
                metadata={},
            )

    def test_content_item_empty_title(self):
        """Test that ContentItem raises ValueError for empty title"""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            ContentItem(
                title="",
                content="Test content",
                source_url="https://example.com",
                published_date=datetime.utcnow(),
                metadata={},
            )

    def test_content_item_empty_content(self):
        """Test that ContentItem raises ValueError for empty content"""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            ContentItem(
                title="Test Title",
                content="",
                source_url="https://example.com",
                published_date=datetime.utcnow(),
                metadata={},
            )


class TestEnhancementResult:
    @pytest.fixture
    def valid_enhancement_result(self):
        return EnhancementResult(
            summary="Test summary",
            key_points=["Point 1", "Point 2"],
            verified_facts=[
                {"fact": "Test fact 1", "confidence": 0.9},
                {"fact": "Test fact 2", "confidence": 0.8},
            ],
            credibility_score=0.85,
            quality_score=0.9,
            processing_metadata={"processing_time": 1.5, "model_version": "1.0.0"},
        )

    def test_enhancement_result_creation(self, valid_enhancement_result):
        """Test that EnhancementResult can be created with valid data"""
        assert valid_enhancement_result.summary == "Test summary"
        assert len(valid_enhancement_result.key_points) == 2
        assert len(valid_enhancement_result.verified_facts) == 2
        assert valid_enhancement_result.credibility_score == 0.85
        assert valid_enhancement_result.quality_score == 0.9
        assert valid_enhancement_result.processing_metadata["processing_time"] == 1.5

    def test_enhancement_result_invalid_score(self):
        """Test that EnhancementResult raises ValueError for invalid scores"""
        with pytest.raises(ValueError, match="Credibility score must be between 0 and 1"):
            EnhancementResult(
                summary="Test",
                key_points=[],
                verified_facts=[],
                credibility_score=1.5,  # Invalid score > 1
                quality_score=0.5,
                processing_metadata={},
            )

        with pytest.raises(ValueError, match="Quality score must be between 0 and 1"):
            EnhancementResult(
                summary="Test",
                key_points=[],
                verified_facts=[],
                credibility_score=0.5,
                quality_score=-0.1,  # Invalid score < 0
                processing_metadata={},
            )

    def test_enhancement_result_empty_summary(self):
        """Test that EnhancementResult raises ValueError for empty summary"""
        with pytest.raises(ValueError, match="Summary cannot be empty"):
            EnhancementResult(
                summary="",
                key_points=["Point 1"],
                verified_facts=[],
                credibility_score=0.5,
                quality_score=0.5,
                processing_metadata={},
            )

    def test_enhancement_result_invalid_facts(self):
        """Test that EnhancementResult validates fact format"""
        with pytest.raises(ValueError, match="Invalid fact format"):
            EnhancementResult(
                summary="Test summary",
                key_points=["Point 1"],
                verified_facts=[{"invalid_key": "value"}],  # Missing required fact fields
                credibility_score=0.5,
                quality_score=0.5,
                processing_metadata={},
            )
