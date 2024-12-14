"""Tests for content summarization functionality."""

import pytest
from unittest.mock import Mock, patch
from feed_processor.content_analysis.summarization import (
    ContentSummarizer,
    SummarizationResult,
    MultiDocSummaryResult
)

@pytest.fixture
def mock_extractive_pipeline():
    """Create mock extractive summarization pipeline."""
    def mock_summarize(text, **kwargs):
        if text == "error":
            raise Exception("Mock error")
        if len(text.split()) <= 5:  
            return [{'summary_text': text}]
        return [{'summary_text': 'Mock extractive summary.'}]
    mock = Mock()
    mock.side_effect = mock_summarize
    return mock

@pytest.fixture
def mock_abstractive_pipeline():
    """Create mock abstractive summarization pipeline."""
    def mock_summarize(text, **kwargs):
        if text == "error":
            raise Exception("Mock error")
        if len(text.split()) <= 5:  
            return [{'summary_text': text}]
        return [{'summary_text': 'Mock abstractive summary.'}]
    mock = Mock()
    mock.side_effect = mock_summarize
    return mock

@pytest.fixture
def summarizer(mock_extractive_pipeline, mock_abstractive_pipeline):
    """Create ContentSummarizer with mock pipelines."""
    with patch('transformers.pipeline') as mock_pipeline:
        def mock_pipeline_factory(model_type, **kwargs):
            if model_type == 'summarization':
                if kwargs.get('model') == 'facebook/bart-large-cnn':
                    return mock_extractive_pipeline
                else:
                    return mock_abstractive_pipeline
            return Mock()
        mock_pipeline.side_effect = mock_pipeline_factory
        summarizer = ContentSummarizer()
        return summarizer

def test_summarize_basic(summarizer):
    """Test basic summarization functionality."""
    text = """
    Artificial intelligence has transformed many industries in recent years.
    Machine learning models can now perform tasks that were once thought impossible.
    Deep learning has revolutionized computer vision and natural language processing.
    These advances have led to breakthroughs in healthcare, finance, and transportation.
    """
    
    result = summarizer.summarize(text)
    
    assert isinstance(result, SummarizationResult)
    assert result.extractive_summary
    assert result.abstractive_summary
    assert isinstance(result.key_points, list)
    assert 0 <= result.confidence_score <= 1
    assert result.compression_ratio > 0
    assert isinstance(result.metadata, dict)

def test_summarize_empty_input(summarizer):
    """Test handling of empty input."""
    with pytest.raises(ValueError):
        summarizer.summarize("")

def test_summarize_short_input(summarizer):
    """Test summarization of very short input."""
    text = "This is a very short text."
    result = summarizer.summarize(text)
    
    assert result.extractive_summary == text
    assert result.compression_ratio == 1.0

def test_summarize_long_input(summarizer):
    """Test summarization of long input."""
    # Create long input text
    long_text = " ".join(["This is sentence number {}.".format(i) for i in range(100)])
    
    result = summarizer.summarize(long_text)
    
    assert len(result.extractive_summary.split()) < len(long_text.split())
    assert result.compression_ratio < 1.0

def test_key_points_extraction(summarizer):
    """Test key points extraction."""
    text = """
    The first major point discusses AI advances.
    The second point covers machine learning applications.
    The third point examines deep learning impact.
    The fourth point looks at future trends.
    """
    
    result = summarizer.summarize(text)
    
    assert len(result.key_points) > 0
    assert all(isinstance(point, str) for point in result.key_points)

def test_confidence_score_calculation(summarizer):
    """Test confidence score calculation."""
    text = "Original text for testing confidence calculation."
    result = summarizer.summarize(text)
    
    assert 0 <= result.confidence_score <= 1
    assert isinstance(result.confidence_score, float)

def test_metadata_contents(summarizer):
    """Test metadata generation."""
    text = "Test text for metadata verification."
    result = summarizer.summarize(text)
    
    required_fields = {
        'original_length',
        'summary_length',
        'compression_ratio',
        'readability_score',
        'coherence_score'
    }
    
    assert all(field in result.metadata for field in required_fields)
    assert all(isinstance(result.metadata[field], (int, float))
              for field in required_fields)

def test_desired_length_parameter(summarizer):
    """Test summarization with desired length parameter."""
    text = "Long text " * 50
    desired_length = 20
    
    result = summarizer.summarize(text, desired_length=desired_length)
    
    assert len(result.extractive_summary.split()) <= desired_length
    assert len(result.abstractive_summary.split()) <= desired_length

def test_error_handling(summarizer):
    """Test error handling in summarization."""
    with pytest.raises(Exception):
        summarizer.summarize("error")

def test_readability_calculation(summarizer):
    """Test readability score calculation."""
    text = "This is a simple test sentence. It has good readability."
    result = summarizer._calculate_readability(text)
    
    assert 0 <= result <= 1
    assert isinstance(result, float)

def test_coherence_calculation(summarizer):
    """Test coherence score calculation."""
    text = """
    First sentence about AI.
    Second sentence about machine learning.
    Third sentence about deep learning.
    """
    result = summarizer._calculate_coherence(text)
    
    assert 0 <= result <= 1
    assert isinstance(result, float)

# Test data for multi-document summarization
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
    """
]

def test_multi_doc_summary_basic(summarizer):
    """Test basic multi-document summarization functionality."""
    result = summarizer.summarize_multiple(
        documents=TEST_ARTICLES,
        desired_length=150
    )
    
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
    assert result.metadata['num_documents'] == len(TEST_ARTICLES)
    assert result.metadata['common_themes_count'] > 0

def test_multi_doc_summary_with_timeline(summarizer):
    """Test multi-document summarization with timeline extraction."""
    result = summarizer.summarize_multiple(
        documents=TEST_ARTICLES,
        desired_length=150,
        identify_timeline=True
    )
    
    # Check timeline
    assert result.timeline is not None
    assert len(result.timeline) > 0
    assert 'date' in result.timeline[0]
    assert 'content' in result.timeline[0]

def test_multi_doc_cross_references(summarizer):
    """Test cross-reference generation between documents."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES)
    
    # Check cross references
    assert len(result.cross_references) > 0
    for ref in result.cross_references:
        assert 'doc1_index' in ref
        assert 'doc2_index' in ref
        assert 'similarity_score' in ref
        assert 0 <= ref['similarity_score'] <= 1

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
        summarizer.summarize_multiple(
            documents=TEST_ARTICLES,
            desired_length=-1
        )

def test_theme_identification(summarizer):
    """Test theme identification across documents."""
    result = summarizer.summarize_multiple(documents=TEST_ARTICLES)
    
    # Check themes
    assert len(result.common_themes) > 0
    assert any('m3' in theme.lower() for theme in result.common_themes)
    assert any('performance' in theme.lower() for theme in result.common_themes)

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
