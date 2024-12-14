"""Tests for content analysis components."""

import pytest
from feed_processor.content_analysis import (
    NLPPipeline,
    CategoryTaxonomy,
    ContentCategorizer,
    SentimentAnalyzer,
    TopicAnalyzer
)
from feed_processor.content_analysis.taxonomy import ContentCategory

@pytest.fixture
def nlp_pipeline():
    """Create NLP pipeline for testing."""
    return NLPPipeline()

@pytest.fixture
def taxonomy():
    """Create category taxonomy for testing."""
    return CategoryTaxonomy()

@pytest.fixture
def categorizer():
    """Create content categorizer for testing."""
    return ContentCategorizer()

@pytest.fixture
def sentiment_analyzer():
    """Create sentiment analyzer for testing."""
    return SentimentAnalyzer()

@pytest.fixture
def topic_analyzer():
    """Create topic analyzer for testing."""
    return TopicAnalyzer()

def test_nlp_pipeline_basic(nlp_pipeline):
    """Test basic NLP pipeline functionality."""
    text = "Apple is developing new artificial intelligence technology."
    result = nlp_pipeline.process_text(text)
    
    assert result.tokens
    assert any("Apple" in ent["text"] for ent in result.entities)
    assert result.language == "en"
    assert len(result.sentences) == 1

def test_nlp_pipeline_keywords(nlp_pipeline):
    """Test keyword extraction."""
    text = "The latest developments in artificial intelligence and machine learning"
    keywords = nlp_pipeline.get_keywords(text)
    
    assert "artificial intelligence" in [k.lower() for k in keywords]
    assert "machine learning" in [k.lower() for k in keywords]

def test_nlp_pipeline_readability(nlp_pipeline):
    """Test readability score calculation."""
    simple_text = "The cat sat on the mat. It was a sunny day."
    complex_text = "The implementation of quantum computing algorithms requires extensive knowledge of advanced mathematical principles and theoretical physics concepts."
    
    simple_score = nlp_pipeline.get_readability_score(simple_text)
    complex_score = nlp_pipeline.get_readability_score(complex_text)
    
    assert 0 <= simple_score <= 100
    assert 0 <= complex_score <= 100
    assert simple_score > complex_score  # Simple text should be more readable

def test_taxonomy_structure(taxonomy):
    """Test category taxonomy structure."""
    tech = taxonomy.get_category("technology")
    assert tech is not None
    
    ai = taxonomy.get_category("ai")
    assert ai is not None
    assert "technology" in taxonomy.get_parent_categories("ai")

def test_taxonomy_keywords(taxonomy):
    """Test category keywords."""
    tech_keywords = taxonomy.get_category_keywords("technology")
    assert "artificial intelligence" in tech_keywords
    assert "machine learning" in tech_keywords

def test_categorizer_basic(categorizer):
    """Test basic content categorization."""
    tech_text = """
    Recent developments in artificial intelligence and machine learning
    have revolutionized the technology industry. Companies like Google
    and Microsoft are investing heavily in AI research and development.
    """
    
    result = categorizer.categorize(tech_text)
    assert result.primary_category == ContentCategory.TECHNOLOGY
    assert result.confidence_scores[ContentCategory.TECHNOLOGY] > 0.7

def test_categorizer_mixed_content(categorizer):
    """Test categorization of mixed content."""
    mixed_text = """
    The stock market responded positively to the announcement of new
    artificial intelligence technology that could revolutionize
    healthcare diagnostics. Investors are particularly interested in
    the potential medical applications.
    """
    
    result = categorizer.categorize(mixed_text)
    # Should detect both business and technology themes
    assert result.primary_category in [ContentCategory.TECHNOLOGY, 
                                     ContentCategory.BUSINESS,
                                     ContentCategory.HEALTH]
    assert len(result.secondary_categories) == 2

def test_categorizer_with_title(categorizer):
    """Test categorization with title."""
    title = "New AI Technology in Healthcare"
    text = """
    Medical professionals are exploring new ways to improve patient
    care through advanced technology. The latest developments show
    promising results in early disease detection.
    """
    
    result = categorizer.categorize(text, title)
    assert any(kw.lower() in ["ai", "healthcare", "technology"] 
              for kw in result.keywords)
    assert result.primary_category in [ContentCategory.HEALTH, 
                                     ContentCategory.TECHNOLOGY]

def test_categorizer_confidence_scores(categorizer):
    """Test confidence scores calculation."""
    text = "Pure technology article about programming and software development."
    result = categorizer.categorize(text)
    
    # Primary category should have highest confidence
    primary_score = result.confidence_scores[result.primary_category]
    assert all(primary_score >= score 
              for cat, score in result.confidence_scores.items()
              if cat != result.primary_category)

def test_categorizer_empty_input(categorizer):
    """Test handling of empty input."""
    result = categorizer.categorize("")
    assert result.primary_category  # Should still return a category
    assert result.confidence_scores  # Should have scores, even if low
    assert result.keywords == []  # No keywords for empty text

def test_sentiment_basic(sentiment_analyzer):
    """Test basic sentiment analysis."""
    positive_text = "This is an excellent product with amazing features."
    negative_text = "The service was terrible and the quality was poor."
    
    positive_result = sentiment_analyzer.analyze(positive_text)
    negative_result = sentiment_analyzer.analyze(negative_text)
    
    assert positive_result.overall_sentiment > 0
    assert negative_result.overall_sentiment < 0
    assert 0 <= positive_result.overall_confidence <= 1
    assert 0 <= negative_result.overall_confidence <= 1

def test_entity_sentiment(sentiment_analyzer):
    """Test entity-level sentiment analysis."""
    text = """
    Apple's new iPhone has excellent features. However, Samsung's latest
    phone has some issues with battery life. Google's AI technology is
    impressive.
    """
    
    entities = [
        {"text": "Apple", "label": "ORG"},
        {"text": "Samsung", "label": "ORG"},
        {"text": "Google", "label": "ORG"}
    ]
    
    result = sentiment_analyzer.analyze(text, entities)
    
    assert len(result.entity_sentiments) == 3
    apple_sentiment = next(es for es in result.entity_sentiments if es.entity == "Apple")
    samsung_sentiment = next(es for es in result.entity_sentiments if es.entity == "Samsung")
    
    assert apple_sentiment.sentiment_score > samsung_sentiment.sentiment_score
    assert all(0 <= es.confidence <= 1 for es in result.entity_sentiments)

def test_aspect_sentiment(sentiment_analyzer):
    """Test aspect-based sentiment analysis."""
    text = """
    The product quality is excellent. However, the performance could be better.
    While it offers good value for money, the reliability is questionable.
    """
    
    result = sentiment_analyzer.analyze(text)
    
    assert "quality" in result.aspect_sentiments
    assert "performance" in result.aspect_sentiments
    assert "reliability" in result.aspect_sentiments
    assert "value" in result.aspect_sentiments
    
    assert result.aspect_sentiments["quality"] > 0
    assert result.aspect_sentiments["reliability"] < 0

def test_sentence_sentiment(sentiment_analyzer):
    """Test sentence-level sentiment analysis."""
    text = """
    The new features are amazing. Unfortunately, the price is too high.
    Overall, it's a good product.
    """
    
    result = sentiment_analyzer.analyze(text)
    
    assert len(result.sentence_sentiments) == 3
    assert result.sentence_sentiments[0][1] > 0  # First sentence positive
    assert result.sentence_sentiments[1][1] < 0  # Second sentence negative
    assert all(-1 <= sentiment <= 1 for _, sentiment in result.sentence_sentiments)

def test_empty_input_sentiment(sentiment_analyzer):
    """Test sentiment analysis with empty input."""
    result = sentiment_analyzer.analyze("")
    
    assert hasattr(result, "overall_sentiment")
    assert hasattr(result, "overall_confidence")
    assert len(result.entity_sentiments) == 0
    assert len(result.sentence_sentiments) == 0

def test_mixed_sentiment(sentiment_analyzer):
    """Test analysis of text with mixed sentiment."""
    text = """
    While the product has some excellent features and great build quality,
    it suffers from poor battery life and occasional software glitches.
    The customer service team is very helpful, but response times are slow.
    """
    
    result = sentiment_analyzer.analyze(text)
    
    # Check for both positive and negative aspects
    assert any(sentiment > 0 for aspect, sentiment in result.aspect_sentiments.items())
    assert any(sentiment < 0 for aspect, sentiment in result.aspect_sentiments.items())
    
    # Check sentence sentiments
    assert any(sentiment > 0 for _, sentiment in result.sentence_sentiments)
    assert any(sentiment < 0 for _, sentiment in result.sentence_sentiments)

def test_topic_extraction_basic(topic_analyzer):
    """Test basic topic extraction."""
    documents = [
        {
            "id": "1",
            "text": "Python is a popular programming language for AI and machine learning."
        },
        {
            "id": "2",
            "text": "Machine learning algorithms are transforming artificial intelligence."
        },
        {
            "id": "3",
            "text": "Deep learning is a subset of machine learning in AI."
        },
        {
            "id": "4",
            "text": "Climate change is affecting global weather patterns."
        },
        {
            "id": "5",
            "text": "Global warming leads to extreme weather events."
        }
    ]
    
    result = topic_analyzer.extract_topics(documents, min_cluster_size=2)
    
    assert len(result.topics) > 0
    assert all(topic.keywords for topic in result.topics)
    assert all(topic.size >= 2 for topic in result.topics)
    assert all(0 <= topic.coherence_score <= 1 for topic in result.topics)

def test_topic_document_assignment(topic_analyzer):
    """Test document to topic assignment."""
    documents = [
        {
            "id": "1",
            "text": "New developments in artificial intelligence and machine learning."
        },
        {
            "id": "2",
            "text": "The latest AI algorithms show promising results."
        }
    ]
    
    result = topic_analyzer.extract_topics(documents, min_cluster_size=2)
    
    assert len(result.document_topics) == 2
    assert "1" in result.document_topics
    assert "2" in result.document_topics
    assert all(0 <= score <= 1 for topics in result.document_topics.values()
              for _, score in topics)

def test_topic_trends(topic_analyzer):
    """Test topic trend analysis."""
    # First batch of documents
    documents1 = [
        {
            "id": "1",
            "text": "AI technology is advancing rapidly."
        },
        {
            "id": "2",
            "text": "Machine learning models are becoming more sophisticated."
        }
    ]
    
    result1 = topic_analyzer.extract_topics(documents1, min_cluster_size=2)
    
    # Second batch with growing topic
    documents2 = documents1 + [
        {
            "id": "3",
            "text": "New breakthroughs in artificial intelligence research."
        },
        {
            "id": "4",
            "text": "AI and machine learning transform industries."
        }
    ]
    
    result2 = topic_analyzer.extract_topics(documents2, min_cluster_size=2)
    
    # Check trend data
    assert result2.topic_trends
    for trend in result2.topic_trends.values():
        assert trend.volume_trend
        assert len(trend.volume_trend) >= 1

def test_emerging_topics(topic_analyzer):
    """Test emerging topics detection."""
    # Initial documents
    initial_docs = [
        {
            "id": str(i),
            "text": f"Document {i} about artificial intelligence."
        } for i in range(3)
    ]
    
    topic_analyzer.extract_topics(initial_docs, min_cluster_size=2)
    
    # Add more documents to create emerging topic
    emerging_docs = initial_docs + [
        {
            "id": str(i),
            "text": f"Document {i} about quantum computing."
        } for i in range(3, 8)
    ]
    
    result = topic_analyzer.extract_topics(emerging_docs, min_cluster_size=2)
    
    assert result.emerging_topics
    assert len(result.emerging_topics) >= 1

def test_related_topics(topic_analyzer):
    """Test related topics detection."""
    documents = [
        # AI/ML cluster
        {
            "id": "1",
            "text": "Artificial intelligence and machine learning advances."
        },
        {
            "id": "2",
            "text": "Deep learning models in AI applications."
        },
        # Data Science cluster
        {
            "id": "3",
            "text": "Data science and statistical analysis methods."
        },
        {
            "id": "4",
            "text": "Machine learning in data science applications."
        }
    ]
    
    result = topic_analyzer.extract_topics(documents, min_cluster_size=2)
    
    # Check for topic relationships
    for topic in result.topics:
        trend = result.topic_trends[topic.id]
        assert trend.related_topics
        # Topics should be related due to shared ML context
        assert len(trend.related_topics) > 0

def test_topic_coherence(topic_analyzer):
    """Test topic coherence calculation."""
    documents = [
        # Coherent cluster
        {
            "id": "1",
            "text": "Python programming language features."
        },
        {
            "id": "2",
            "text": "Advanced Python programming techniques."
        },
        # Less coherent cluster
        {
            "id": "3",
            "text": "Weather patterns and climate change."
        },
        {
            "id": "4",
            "text": "Economic impact of environmental policies."
        }
    ]
    
    result = topic_analyzer.extract_topics(documents, min_cluster_size=2)
    
    coherence_scores = [topic.coherence_score for topic in result.topics]
    assert len(coherence_scores) >= 2
    assert all(0 <= score <= 1 for score in coherence_scores)
    # Coherent cluster should have higher score
    assert max(coherence_scores) > 0.5
