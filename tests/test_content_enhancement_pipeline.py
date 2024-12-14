"""Tests for the content enhancement pipeline.

This module contains test cases for the content enhancement pipeline,
which processes and enhances content items with additional information.
"""

from datetime import datetime, timezone
from unittest import mock

import pytest

from feed_processor.content_enhancement.pipeline import ContentEnhancementPipeline
from feed_processor.storage.models import ContentItem, ContentType


class TestContentEnhancementPipeline:
    """Test suite for the ContentEnhancementPipeline class.

    Tests content processing, quality scoring, fact verification,
    and other pipeline functionality.
    """

    @pytest.fixture
    def pipeline(self):
        """Create a ContentEnhancementPipeline instance for testing."""
        return ContentEnhancementPipeline(min_content_length=10)

    @pytest.fixture
    def valid_content_item(self):
        """Create a valid content item for testing."""
        return ContentItem(
            id="test-123",
            title="Test Article",
            content=("This is a test article with sufficient content for processing."),
            url="https://example.com/test",
            published_at=datetime.now(timezone.utc),
            content_type=ContentType.ARTICLE,
            metadata={},
        )

    @pytest.fixture
    def short_content_item(self):
        """Create a content item with insufficient content."""
        return ContentItem(
            id="test-456",
            title="Short Test",
            content="Too short",
            url="https://example.com/short",
            published_at=datetime.now(timezone.utc),
            content_type=ContentType.ARTICLE,
            metadata={},
        )

    @pytest.mark.asyncio
    async def test_process_valid_content(self, pipeline, valid_content_item):
        """Test processing of valid content."""
        result = await pipeline.process_item(valid_content_item)

        assert result is not None
        assert result["id"] == valid_content_item.id
        assert result["title"] == valid_content_item.title
        assert result["url"] == valid_content_item.url
        assert "summary" in result
        assert "facts" in result
        assert "quality_score" in result
        assert 0 <= result["quality_score"] <= 1

    @pytest.mark.asyncio
    async def test_process_short_content(self, pipeline, short_content_item):
        """Test processing of content that's too short."""
        result = await pipeline.process_item(short_content_item)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_empty_content(self, pipeline):
        """Test processing of empty content."""
        empty_item = ContentItem(
            id="test-789",
            title="Empty Test",
            content="",
            url="https://example.com/empty",
            published_at=datetime.now(timezone.utc),
            content_type=ContentType.ARTICLE,
            metadata={},
        )
        result = await pipeline.process_item(empty_item)
        assert result is None

    @pytest.mark.asyncio
    async def test_quality_score_calculation(self, pipeline, valid_content_item):
        """Test quality score calculation."""
        result = await pipeline.process_item(valid_content_item)
        assert result is not None
        assert "quality_score" in result
        assert 0 <= result["quality_score"] <= 1

    @pytest.mark.asyncio
    async def test_metadata_enhancement(self, pipeline, valid_content_item):
        """Test metadata enhancement."""
        result = await pipeline.process_item(valid_content_item)
        assert result is not None
        assert "metadata" in result
        assert "quality_score" in result["metadata"]
        assert "has_summary" in result["metadata"]
        assert "fact_count" in result["metadata"]

    @pytest.mark.asyncio
    async def test_content_validation(self, pipeline):
        """Test content validation with various inputs."""
        test_cases = [
            ("", False),  # Empty content
            ("x" * 5, False),  # Too short
            ("x" * 100, True),  # Valid length
        ]

        for content, expected in test_cases:
            item = ContentItem(
                id="test",
                title="Test",
                content=content,
                url="https://example.com",
                published_at=datetime.now(timezone.utc),
                content_type=ContentType.ARTICLE,
                metadata={},
            )
            assert pipeline._validate_content(item) == expected

    @pytest.mark.asyncio
    async def test_summary_generation(self, pipeline):
        """Test summary generation with different content lengths."""
        short_content = "Short content."
        long_content = "Long content. " * 50

        short_summary = pipeline._generate_summary(short_content)
        long_summary = pipeline._generate_summary(long_content)

        assert short_summary == short_content
        assert len(long_summary) <= 203  # 200 chars + "..."
        assert long_summary.endswith("...")

    @pytest.mark.asyncio
    async def test_process_content_success(self, pipeline, valid_content_item):
        """Test successful content processing."""
        # Mock fact extraction and verification
        pipeline.llm_manager.generate_summary.return_value = "Test summary"
        pipeline.llm_manager.extract_facts.return_value = "Fact 1\nFact 2"

        # Mock fact verification with high confidence
        pipeline.fact_checker.verify_fact.return_value = mock.Mock(
            confidence=0.9, verified=True, source="test"
        )

        result = await pipeline.process_item(valid_content_item)

        # Verify the result
        assert isinstance(result, dict)
        assert result["summary"] == "Test summary"
        assert len(result["facts"]) > 0  # Should have verified facts
        assert result["quality_score"] > 0  # Should have positive quality score

        # Verify method calls
        pipeline.llm_manager.generate_summary.assert_called_once()
        pipeline.llm_manager.extract_facts.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_content_failure(self, pipeline, valid_content_item):
        """Test content processing with failed quality check."""
        pipeline._passes_quality_check = mock.Mock(return_value=False)
        result = await pipeline.process_item(valid_content_item)
        assert result is None
        pipeline.metrics_collector.increment.assert_called_with("quality_check_failed")

    @pytest.mark.asyncio
    async def test_summary_coherence_check(self, pipeline, valid_content_item):
        """Test summary coherence checking."""
        # Test with high coherence summary
        good_summary = (
            "AI has progressed significantly, with ML models achieving remarkable "
            "results and NLP seeing impressive advances."
        )
        coherence_score = await pipeline._check_summary_coherence(good_summary, valid_content_item)
        assert coherence_score >= 0.7

        # Test with low coherence summary
        bad_summary = (
            "Quantum computers use qubits for computation. "
            "Space exploration has reached new frontiers."
        )
        coherence_score = await pipeline._check_summary_coherence(bad_summary, valid_content_item)
        assert coherence_score < 0.7

        # Test error handling
        pipeline.llm_manager.generate_summary.side_effect = Exception("API Error")
        coherence_score = await pipeline._check_summary_coherence(good_summary, valid_content_item)
        assert coherence_score == 0.8  # Default score on error

    @pytest.mark.asyncio
    async def test_summary_refinement(self, pipeline, valid_content_item):
        """Test the summary refinement process.

        Verifies that the pipeline can successfully refine summaries by making them
        more coherent and detailed.
        """
        original_summary = "AI makes progress. ML does things. NLP is good."
        refined_summary = (
            "AI has made significant progress, with ML models achieving "
            "remarkable results in various domains."
        )

        # Mock successful refinement
        pipeline.llm_manager.generate_summary.return_value = refined_summary
        result = await pipeline._refine_summary(original_summary, valid_content_item)
        assert result == refined_summary

        # Test error handling
        pipeline.llm_manager.generate_summary.side_effect = Exception("API Error")
        result = await pipeline._refine_summary(original_summary, valid_content_item)
        assert result == original_summary  # Falls back to original on error

    @pytest.mark.asyncio
    async def test_fact_categorization(self, pipeline, valid_content_item):
        """Test fact categorization functionality."""
        # Test statistical fact
        stat_fact = "Machine learning models have achieved 95% accuracy."
        category = await pipeline._categorize_fact(stat_fact)
        assert category == "STATISTICAL"

        # Test temporal fact
        time_fact = "AI developments in recent years have been significant."
        category = await pipeline._categorize_fact(time_fact)
        assert category == "TEMPORAL"

        # Test error handling
        pipeline.llm_manager.generate_summary.side_effect = Exception("API Error")
        category = await pipeline._categorize_fact(stat_fact)
        assert category == "GENERAL"  # Default category on error

    def test_source_context_finding(self, pipeline, valid_content_item):
        """Test source context extraction."""
        # Test exact match
        fact = "Machine learning models have achieved remarkable results"
        context = pipeline._find_source_context(fact, valid_content_item.content)
        assert context and fact in context

        # Test partial match
        fact = "learning models achieve results"
        context = pipeline._find_source_context(fact, valid_content_item.content)
        assert context and "learning models" in context

        # Test no match
        fact = "This fact does not exist in the content"
        context = pipeline._find_source_context(fact, valid_content_item.content)
        assert context is None

    def test_quality_scoring(self, pipeline, valid_content_item):
        """Test enhanced quality scoring system."""
        summary = (
            "AI has made significant progress in recent years, with machine "
            "learning models achieving remarkable results. NLP advancements "
            "have been particularly notable, especially in text generation."
        ).strip()

        verified_facts = [
            {"fact": "AI has made progress", "confidence": 0.9, "category": "DESCRIPTIVE"},
            {"fact": "ML models achieve results", "confidence": 0.8, "category": "RELATIONAL"},
            {"fact": "NLP has advanced", "confidence": 0.95, "category": "TEMPORAL"},
        ]

        credibility_score = 0.85

        # Test length score
        length_score = pipeline._calculate_length_score(summary)
        assert 0 <= length_score <= 1
        assert length_score > 0.7  # Good length

        # Test facts score
        facts_score = pipeline._calculate_facts_score(verified_facts)
        assert 0 <= facts_score <= 1
        assert facts_score > 0.6  # Good fact diversity and confidence

        # Test readability score
        readability_score = pipeline._calculate_readability_score(summary)
        assert 0 <= readability_score <= 1
        assert readability_score > 0.7  # Good readability

        # Test relevance score
        relevance_score = pipeline._calculate_relevance_score(summary, valid_content_item)
        assert 0 <= relevance_score <= 1
        assert relevance_score > 0.6  # Good relevance

        # Test overall quality score
        quality_score = pipeline._calculate_quality_score(
            valid_content_item, summary, verified_facts, credibility_score
        )
        assert 0 <= quality_score <= 1
        assert quality_score > 0.7  # Good overall quality

    def test_readability_scoring_edge_cases(self, pipeline):
        """Test readability scoring with edge cases."""
        # Empty text
        score = pipeline._calculate_readability_score("")
        assert score == 0.0

        # Single word
        score = pipeline._calculate_readability_score("Word")
        assert score > 0

        # Very long sentences
        long_text = "This is a very long sentence with many words that goes on and on " * 10
        score = pipeline._calculate_readability_score(long_text)
        assert score < 0.5  # Penalized for long sentences

        # Short, simple sentences
        simple_text = "This is good. It is clear. The point is made."
        score = pipeline._calculate_readability_score(simple_text)
        assert score > 0.8  # Rewarded for clarity

    def test_relevance_scoring_edge_cases(self, pipeline, valid_content_item):
        """Test relevance scoring with edge cases."""
        # Create test content items
        empty_content = ContentItem(
            id="test-2",
            title="",
            content="",
            url="https://test.com/empty",
            published_at=datetime.now(timezone.utc),
            content_type=ContentType.ARTICLE,
            metadata={},
        )

        # Test empty content and summary
        score = pipeline._calculate_relevance_score("", empty_content)
        assert score == 0.8  # Default score on error

        # Test completely irrelevant summary
        irrelevant_summary = "Something completely unrelated to the content"
        score = pipeline._calculate_relevance_score(irrelevant_summary, valid_content_item)
        assert score < 0.3  # Low relevance score

        # Test highly relevant summary
        relevant_summary = "Artificial Intelligence and Machine Learning progress"
        score = pipeline._calculate_relevance_score(relevant_summary, valid_content_item)
        assert score > 0.7  # High relevance score
