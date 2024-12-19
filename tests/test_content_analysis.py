"""Tests for content analysis package."""

from feed_processor.content_analysis import (
    CategoryTaxonomy,
    ContentCategorizer,
    SentimentAnalyzer,
    TopicAnalyzer,
)
from feed_processor.content_analysis.nlp_pipeline import NLPPipeline


def test_nlp_pipeline_basic():
    """Test basic NLP pipeline functionality."""
    pipeline = NLPPipeline()
    text = "This is a test sentence with some important keywords."

    result = pipeline.process_text(text)
    assert result.sentences
    assert result.tokens
    assert result.lemmas
    assert result.pos_tags
    assert result.noun_phrases
    assert result.keywords
    assert result.entities


def test_nlp_pipeline_keywords():
    """Test keyword extraction."""
    pipeline = NLPPipeline()
    text = "Python is a great programming language. Developers love Python."
    result = pipeline.process_text(text)

    assert "python" in [kw.lower() for kw in result.keywords]
    assert "programming" in [kw.lower() for kw in result.keywords]


def test_nlp_pipeline_noun_phrases():
    """Test noun phrase extraction."""
    pipeline = NLPPipeline()
    text = "This is a simple test sentence. Another simple sentence."
    result = pipeline.process_text(text)

    assert result.noun_phrases
    assert isinstance(result.noun_phrases, list)
    assert all(isinstance(np, str) for np in result.noun_phrases)


def test_taxonomy_structure():
    """Test taxonomy structure."""
    taxonomy = CategoryTaxonomy()
    root = taxonomy.root

    assert root.name == "root"
    assert len(root.children) > 0
    assert all(child.parent == root for child in root.children)


def test_taxonomy_keywords():
    """Test taxonomy keywords."""
    taxonomy = CategoryTaxonomy()
    tech_category = taxonomy.get_category_by_name("Technology")

    assert tech_category
    assert tech_category.keywords
    assert "technology" in tech_category.keywords


def test_categorizer_basic():
    """Test basic categorization."""
    categorizer = ContentCategorizer()
    text = (
        "Python is a popular programming language used in "
        "artificial intelligence and machine learning."
    )
    result = categorizer.categorize(text)

    assert result.primary_category
    assert result.confidence_scores[result.primary_category.name] > 0.7
    assert len(result.categories) >= 1


def test_categorizer_mixed_content():
    """Test categorization with mixed content."""
    categorizer = ContentCategorizer()
    text = """
    The new AI model shows promising results in medical diagnosis.
    The startup secured $10M in funding for their healthcare technology.
    """
    result = categorizer.categorize(text)

    assert result.primary_category
    assert len(result.secondary_categories) == 2


def test_categorizer_with_title():
    """Test categorization with title."""
    categorizer = ContentCategorizer()
    text = "The model shows promising results in various applications."
    title = "New AI Technology Breakthrough"
    result = categorizer.categorize(text, title=title)

    assert result.primary_category
    assert "technology" in result.primary_category.name.lower()


def test_categorizer_confidence_scores():
    """Test confidence scores in categorization."""
    categorizer = ContentCategorizer()
    text = "AI and machine learning are transforming industries"
    categories = categorizer.categorize(text)

    assert all(0 <= cat.confidence <= 1.0 for cat in categories)


def test_categorizer_empty_input():
    """Test categorization with empty input."""
    categorizer = ContentCategorizer()
    result = categorizer.categorize("")

    assert result.primary_category  # Should still return a category
    assert result.confidence_scores  # Should have default scores


def test_sentiment_basic():
    """Test basic sentiment analysis."""
    analyzer = SentimentAnalyzer()
    text = "AI is making great progress in technology"
    result = analyzer.analyze(text)

    assert result.overall_sentiment in [-1, 0, 1]
    assert result.confidence > 0


def test_entity_sentiment():
    """Test entity-level sentiment."""
    analyzer = SentimentAnalyzer()
    text = "Apple products are great but Microsoft software has issues."
    entities = ["Apple", "Microsoft"]
    result = analyzer.analyze(text, entities=entities)

    assert "Apple" in result.entity_sentiments
    assert "Microsoft" in result.entity_sentiments
    assert result.entity_sentiments["Apple"] > result.entity_sentiments["Microsoft"]


def test_aspect_sentiment():
    """Test aspect-based sentiment."""
    analyzer = SentimentAnalyzer()
    text = "The performance is excellent but reliability is terrible."
    aspects = ["performance", "reliability"]
    result = analyzer.analyze(text, aspects=aspects)

    assert result.aspect_sentiments["performance"] > 0
    assert result.aspect_sentiments["reliability"] < 0


def test_sentence_sentiment():
    """Test sentence-level sentiment."""
    analyzer = SentimentAnalyzer()
    text = "I love this! But I hate that."
    result = analyzer.analyze(text)

    assert len(result.sentence_sentiments) == 2
    assert result.sentence_sentiments[0][1] > 0  # First sentence positive
    assert result.sentence_sentiments[1][1] < 0  # Second sentence negative


def test_empty_input_sentiment():
    """Test sentiment analysis with empty input."""
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze("")

    assert result.overall_sentiment == 0
    assert not result.sentence_sentiments
    assert not result.entity_sentiments
    assert not result.aspect_sentiments


def test_mixed_sentiment():
    """Test sentiment analysis with mixed sentiment."""
    analyzer = SentimentAnalyzer()
    text = """
    The interface is beautiful and user-friendly.
    However, the system performance is slow and unreliable.
    Customer service was helpful but pricing is too expensive.
    """
    aspects = ["interface", "performance", "service", "pricing"]
    result = analyzer.analyze(text, aspects=aspects)

    assert result.overall_sentiment != 0  # Should have non-zero overall sentiment
    assert any(sentiment > 0 for aspect, sentiment in result.aspect_sentiments.items())
    assert any(sentiment < 0 for aspect, sentiment in result.aspect_sentiments.items())


def test_topic_extraction_basic():
    """Test basic topic extraction."""
    analyzer = TopicAnalyzer()
    docs = [
        "AI and machine learning applications",
        "Machine learning in data science",
        "AI technology trends",
    ]
    result = analyzer.extract_topics(docs)

    assert result.topics
    assert len(result.topics) > 0
    assert all(topic.keywords for topic in result.topics)


def test_topic_document_assignment():
    """Test topic-document assignment."""
    analyzer = TopicAnalyzer()
    docs = ["Machine learning applications", "Deep learning models", "Neural networks"]
    result = analyzer.extract_topics(docs)

    assert result.document_topics
    assert all(len(topics) > 0 for topics in result.document_topics.values())


def test_topic_trends():
    """Test topic trend analysis."""
    analyzer = TopicAnalyzer()
    documents1 = [
        "AI is transforming industries",
        "Machine learning applications",
    ]
    documents2 = [
        "AI revolution in technology",
        "AI and machine learning growth",
        "Future of AI technology",
    ]

    result1 = analyzer.extract_topics(documents1, min_cluster_size=2)
    result2 = analyzer.extract_topics(documents2, min_cluster_size=2)

    assert result2.topics
    assert len(result2.topics) >= len(result1.topics)


def test_emerging_topics():
    """Test emerging topics detection."""
    analyzer = TopicAnalyzer()
    initial_docs = [
        "Traditional software development",
        "Programming basics",
    ]
    new_docs = [
        "AI is transforming industries",
        "Machine learning revolution",
        "AI applications growing",
    ]

    # Train on initial docs
    analyzer.extract_topics(initial_docs, min_cluster_size=2)

    # Analyze new docs
    result = analyzer.extract_topics(new_docs, min_cluster_size=2)

    assert result.emerging_topics
    assert any("ai" in topic.name.lower() for topic in result.emerging_topics)


def test_related_topics():
    """Test related topics detection."""
    analyzer = TopicAnalyzer()
    documents = [
        "AI and machine learning applications",
        "Deep learning and neural networks",
        "Machine learning and data science",
        "AI technology trends",
    ]
    result = analyzer.extract_topics(documents, min_cluster_size=2)

    assert result.related_topics
    assert any(len(related) > 0 for related in result.related_topics.values())


def test_topic_coherence():
    """Test topic coherence calculation."""
    analyzer = TopicAnalyzer()
    documents = [
        "AI and machine learning are related technologies",
        "Deep learning is part of machine learning",
        "AI applications use machine learning",
        "Technology trends in AI and ML",
    ]
    result = analyzer.extract_topics(documents, min_cluster_size=2)

    assert result.topic_coherence >= 0
    assert result.topic_coherence <= 1
