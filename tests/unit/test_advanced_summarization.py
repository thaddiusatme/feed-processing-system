"""Unit tests for the advanced summarization functionality."""

from datetime import datetime, timedelta

import pytest

from feed_processor.content_analysis.advanced_summarization import AdvancedSummarizer
from feed_processor.content_analysis.summarization import SummarizationResult


class MockSummarizer:
    """Mock summarizer for testing."""

    def __init__(self):
        """Initialize the mock summarizer."""
        self.max_length = 150
        self.min_length = 50

    def summarize(self, text: str) -> SummarizationResult:
        """Generate a summary preserving key terms for consistent testing.

        Args:
            text: The input text to summarize.

        Returns:
            SummarizationResult containing the generated summary.
        """
        summary = f"Summary about {' '.join(text.split()[:5])}..."
        return SummarizationResult(
            extractive_summary=summary,
            abstractive_summary=summary,
            key_points=["Key point 1", "Key point 2"],
            summary_length=len(summary),
            compression_ratio=0.5,
            confidence_score=0.8,
            metadata={"mock": True},
            sentiment_score=0.5,
        )


def mock_pipeline(text: str) -> str:
    """Mock pipeline for testing."""
    return f"Mock combined summary of: {text[:50]}..."


@pytest.fixture
def summarizer():
    """Create a mock content summarizer for testing."""
    return MockSummarizer()


@pytest.fixture
def advanced_summarizer(summarizer):
    """Create an advanced summarizer with mocks for testing."""
    return AdvancedSummarizer(base_summarizer=summarizer, mock_pipeline=mock_pipeline)


@pytest.fixture
def sample_documents():
    """Create sample documents for testing."""
    return [
        """
        The new AI model has shown remarkable performance in natural language tasks.
        Researchers report significant improvements in translation and summarization.
        The model was trained on a diverse dataset of multilingual content.
        """,
        """
        Building on previous research, the latest AI breakthrough demonstrates
        enhanced capabilities in language processing. The model excels particularly
        in translation tasks, showing a 20% improvement over baseline.
        """,
        """
        Critics raise concerns about the environmental impact of training large AI
        models. The energy consumption and computational resources required for
        training these models have significant environmental costs.
        """,
    ]


@pytest.fixture
def sample_metadata():
    """Create sample metadata for testing."""
    base_date = datetime.now()
    return [
        {
            "date": base_date - timedelta(days=2),
            "source": "Tech Journal",
            "id": "doc1",
        },
        {
            "date": base_date - timedelta(days=1),
            "source": "AI Research Weekly",
            "id": "doc2",
        },
        {
            "date": base_date,
            "source": "Environmental Science",
            "id": "doc3",
        },
    ]


def test_multi_document_summarize(advanced_summarizer, sample_documents):
    """Test multi-document summarization."""
    result = advanced_summarizer.multi_document_summarize(sample_documents)

    assert result is not None
    assert result.extractive_summary.startswith("Mock combined summary")
    assert result.abstractive_summary.startswith("Mock combined summary")
    assert len(result.key_points) > 0
    assert len(result.common_themes) > 0
    assert len(result.document_summaries) == len(sample_documents)


def test_multi_document_summarize_with_metadata(
    advanced_summarizer, sample_documents, sample_metadata
):
    """Test multi-document summarization with metadata."""
    result = advanced_summarizer.multi_document_summarize(sample_documents, sample_metadata)

    assert result is not None
    assert result.timeline is not None
    assert len(result.timeline) == len(sample_documents)
    assert all("date" in entry for entry in result.timeline)


def test_cross_references(advanced_summarizer, sample_documents):
    """Test cross-reference generation."""
    # Use very similar documents that share key terms
    similar_docs = [
        "AI and machine learning advances in NLP research",
        "Machine learning and AI progress in NLP studies",
        "Environmental impact of cloud computing",  # Different topic
    ]
    result = advanced_summarizer.multi_document_summarize(similar_docs)

    assert result.cross_references is not None
    # First two documents should have high similarity
    cross_refs = [
        ref
        for ref in result.cross_references
        if (ref["source_idx"] == 0 and ref["target_idx"] == 1)
        or (ref["source_idx"] == 1 and ref["target_idx"] == 0)
    ]
    assert len(cross_refs) > 0
    assert all(ref["similarity"] > 0.5 for ref in cross_refs)


def test_common_themes(advanced_summarizer, sample_documents):
    """Test common theme extraction."""
    result = advanced_summarizer.multi_document_summarize(sample_documents)

    assert result.common_themes is not None
    assert len(result.common_themes) > 0
    # Check if "AI" and "model" are in the common themes
    common_themes_text = " ".join(result.common_themes).lower()
    assert "ai" in common_themes_text or "model" in common_themes_text


def test_empty_documents(advanced_summarizer):
    """Test handling of empty document list."""
    with pytest.raises(ValueError):
        advanced_summarizer.multi_document_summarize([])


def test_single_document(advanced_summarizer, sample_documents):
    """Test handling of single document."""
    result = advanced_summarizer.multi_document_summarize([sample_documents[0]])

    assert result is not None
    assert result.extractive_summary.startswith("Mock combined summary")
    assert len(result.document_summaries) == 1
    assert not result.cross_references  # No cross-references with single document


def test_timeline_sorting(advanced_summarizer, sample_documents, sample_metadata):
    """Test timeline sorting in chronological order."""
    result = advanced_summarizer.multi_document_summarize(sample_documents, sample_metadata)

    assert result.timeline is not None
    dates = [entry["date"] for entry in result.timeline]
    assert dates == sorted(dates)  # Check if dates are in ascending order
