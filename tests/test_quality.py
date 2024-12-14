"""Tests for content quality scoring functionality."""
import pytest
from unittest.mock import Mock

from feed_processor.content_analysis.quality import ContentQualityScorer
from feed_processor.content_analysis.nlp_pipeline import NLPPipeline
from feed_processor.content_analysis.sentiment import SentimentAnalyzer

@pytest.fixture
def mock_nlp_pipeline():
    nlp = Mock(spec=NLPPipeline)
    nlp.calculate_readability.return_value = 0.8
    nlp.extract_keywords.return_value = ["key1", "key2"]
    return nlp

@pytest.fixture
def mock_sentiment_analyzer():
    sentiment = Mock(spec=SentimentAnalyzer)
    sentiment.analyze_text.return_value = Mock(compound_score=0.5)
    return sentiment

@pytest.fixture
def quality_scorer(mock_nlp_pipeline, mock_sentiment_analyzer):
    return ContentQualityScorer(mock_nlp_pipeline, mock_sentiment_analyzer)

def test_score_content_basic(quality_scorer):
    """Test basic content scoring functionality."""
    text = "This is a test article about content quality. It contains multiple sentences and some facts."
    
    result = quality_scorer.score_content(text)
    
    assert 0 <= result.overall_score <= 1
    assert 0 <= result.readability_score <= 1
    assert 0 <= result.sentiment_score <= 1
    assert 0 <= result.coherence_score <= 1
    assert 0 <= result.engagement_score <= 1
    assert 0 <= result.originality_score <= 1
    assert 0 <= result.fact_density <= 1
    assert isinstance(result.quality_flags, list)
    assert isinstance(result.detailed_metrics, dict)

def test_score_content_empty(quality_scorer):
    """Test scoring empty content."""
    with pytest.raises(RuntimeError):
        quality_scorer.score_content("")

def test_score_content_long(quality_scorer):
    """Test scoring longer, more complex content."""
    text = """
    This is a comprehensive article about artificial intelligence and its impact on society.
    The technology has evolved significantly over the past decade. Many experts believe that
    AI will transform industries like healthcare, finance, and transportation. However, there
    are also concerns about ethical implications and potential job displacement. Recent studies
    show that 60% of companies are investing in AI technologies. The future remains uncertain,
    but the potential benefits are substantial.
    """
    
    result = quality_scorer.score_content(text)
    
    assert result.overall_score > 0.5  # Expect decent score for well-structured content
    assert len(result.detailed_metrics) > 0
    assert 'sentence_count' in result.detailed_metrics
    assert 'avg_sentence_length' in result.detailed_metrics

def test_quality_flags(quality_scorer):
    """Test quality flag generation for problematic content."""
    repetitive_text = "The cat saw a cat. The cat jumped. The cat ran. The cat slept."
    
    result = quality_scorer.score_content(repetitive_text)
    
    assert "excessive_repetition" in result.quality_flags

def test_fact_density(quality_scorer):
    """Test fact density calculation."""
    factual_text = "In 2023, Apple released the iPhone 15 in California. The device costs $999."
    
    result = quality_scorer.score_content(factual_text)
    
    assert result.fact_density > 0.3  # Expect higher fact density due to numbers and entities

def test_engagement_score(quality_scorer):
    """Test engagement score calculation."""
    engaging_text = "Have you ever wondered about space exploration? NASA's recent Mars mission revealed fascinating discoveries! Scientists are now planning the next phase."
    
    result = quality_scorer.score_content(engaging_text)
    
    assert result.engagement_score > 0.4  # Expect higher engagement due to questions and varied structure
