"""Tests for multi-document summarization functionality."""

import pytest

from feed_processor.content_analysis.summarization import ContentSummarizer, MultiDocSummaryResult

# Test documents about a technology announcement
TEST_ARTICLES = [
    """
    Apple today announced its latest M3 chip series, marking a significant leap in
    Mac performance. The new chips, built on 3-nanometer technology, offer up to
    60% faster CPU performance than M1. The company claims these processors will
    revolutionize professional workflows and gaming on Mac platforms.
    """,
    """
    Industry analysts predict Apple's new M3 chips will significantly impact the
    PC market. Benchmark tests show the M3 outperforming competing processors in
    both performance and energy efficiency. The 3nm manufacturing process gives
    Apple a temporary advantage in the market, as competitors are still using 5nm
    technology.
    """,
    """
    Software developers are rapidly updating their applications to take advantage
    of Apple's M3 architecture. Professional tools like Adobe Creative Suite and
    DaVinci Resolve have announced optimized versions coming in December 2023.
    Gaming companies are also showing increased interest in Mac development due
    to the M3's enhanced graphics capabilities.
    """,
]


@pytest.fixture
def summarizer():
    return ContentSummarizer()


def test_multi_doc_summary_basic(summarizer):
    """Test basic multi-document summarization functionality."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES, desired_length=150)

    # Check result type
    assert isinstance(result, MultiDocSummaryResult)

    # Check summary content
    assert len(result.extractive_summary) > 0
    assert len(result.abstractive_summary) > 0
    assert len(result.key_points) > 0
    assert len(result.common_themes) > 0

    # Check metrics
    assert 0 <= result.confidence_score <= 1
    assert result.compression_ratio > 0

    # Check metadata
    assert result.metadata["num_documents"] == len(TEST_ARTICLES)
    assert result.metadata["common_themes_count"] > 0


def test_multi_doc_summary_with_timeline(summarizer):
    """Test multi-document summarization with timeline extraction."""
    result = summarizer.summarize_multiple(
        documents=TEST_ARTICLES, desired_length=150, identify_timeline=True
    )

    # Check timeline
    assert result.timeline is not None
    assert len(result.timeline) > 0
    assert "date" in result.timeline[0]
    assert "content" in result.timeline[0]


def test_multi_doc_cross_references(summarizer):
    """Test cross-reference generation between documents."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES)

    # Check cross references
    assert len(result.cross_references) > 0
    for ref in result.cross_references:
        assert "doc1_index" in ref
        assert "doc2_index" in ref
        assert "similarity_score" in ref
        assert 0 <= ref["similarity_score"] <= 1


def test_empty_documents(summarizer):
    """Test handling of empty documents."""
    with pytest.raises(ValueError):
        summarizer.summarize_multiple(documents=[])


def test_single_document(summarizer):
    """Test multi-document summarization with single document."""
    result = summarizer.summarize_multiple(documents=[TEST_ARTICLES[0]])

    assert isinstance(result, MultiDocSummaryResult)
    assert len(result.cross_references) == 0
    assert len(result.document_summaries) == 1


def test_invalid_desired_length(summarizer):
    """Test handling of invalid desired length."""
    with pytest.raises(ValueError):
        summarizer.summarize_multiple(documents=TEST_ARTICLES, desired_length=-1)


def test_theme_identification(summarizer):
    """Test theme identification across documents."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES)

    # Check themes
    assert len(result.common_themes) > 0
    assert any("m3" in theme.lower() for theme in result.common_themes)
    assert any("performance" in theme.lower() for theme in result.common_themes)


def test_key_points_extraction(summarizer):
    """Test key points extraction from multiple documents."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES)

    # Check key points
    assert len(result.key_points) > 0
    assert len(result.key_points) <= 5  # Should not exceed max key points


def test_large_documents(summarizer):
    """Test handling of large documents."""
    large_docs = [doc * 10 for doc in TEST_ARTICLES]  # Make documents 10x larger
    result = summarizer.summarize_multiple(documents=large_docs)

    assert len(result.extractive_summary) > 0
    assert result.compression_ratio < 1.0
