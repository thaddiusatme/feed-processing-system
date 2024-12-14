"""Tests for the content enrichment module."""

import logging
from unittest.mock import Mock, patch

import pytest

from feed_processor.content_analysis.enrichment import ContentEnricher, Entity, FactCheck

# Configure logging for tests
logging.basicConfig(level=logging.INFO)


@pytest.fixture
def enricher():
    return ContentEnricher()


@pytest.fixture
def sample_text():
    return """
    Apple Inc. CEO Tim Cook announced new iPhone models yesterday in California.
    The company claims the new devices will have 20% better battery life.
    """


def test_entity_identification(enricher, sample_text):
    entities = enricher.identify_and_link_entities(sample_text)
    assert len(entities) > 0

    # Check if common entities are identified
    entity_texts = {e.text.lower() for e in entities}
    entity_labels = {(e.text.lower(), e.label) for e in entities}

    # Check for organization entities
    assert any(
        text in ["apple", "apple inc.", "apple inc"]
        for text, label in entity_labels
        if label == "ORG"
    )

    # Check for person entities
    assert any(
        text in ["tim cook", "tim", "cook"] for text, label in entity_labels if label == "PERSON"
    )

    # Check for location entities
    assert any(text == "california" for text, label in entity_labels if label == "GPE")


def test_fact_verification(enricher):
    claims = ["The Earth orbits around the Sun.", "The Moon is made of cheese."]
    fact_checks = enricher.verify_facts(claims)

    assert len(fact_checks) == 2
    assert all(isinstance(fc, FactCheck) for fc in fact_checks)
    assert all(hasattr(fc, "verification_status") for fc in fact_checks)
    assert all(hasattr(fc, "confidence") for fc in fact_checks)


@patch("wikipedia.search")
@patch("wikipedia.page")
def test_entity_linking_with_wikipedia(mock_page, mock_search, enricher):
    mock_search.return_value = ["Apple Inc."]
    mock_page.return_value = Mock(
        url="https://en.wikipedia.org/wiki/Apple_Inc.",
        summary="Apple Inc. is a technology company.",
    )

    entities = enricher.identify_and_link_entities("Apple announced new products.")

    assert len(entities) > 0
    apple_entity = next((e for e in entities if "apple" in e.text.lower()), None)
    assert apple_entity is not None
    assert apple_entity.kb_id == "https://en.wikipedia.org/wiki/Apple_Inc."


def test_process_content(enricher, sample_text):
    result = enricher.process_content(sample_text)

    assert "entities" in result
    assert "fact_checks" in result
    assert "metadata" in result

    assert isinstance(result["entities"], list)
    assert isinstance(result["fact_checks"], list)
    assert isinstance(result["metadata"], dict)

    assert "entity_count" in result["metadata"]
    assert "fact_check_count" in result["metadata"]


def test_entity_properties():
    entity = Entity(
        text="Apple",
        label="ORG",
        kb_id="https://en.wikipedia.org/wiki/Apple_Inc.",
        confidence=0.95,
        description="Technology company",
        links={"wikipedia": "https://en.wikipedia.org/wiki/Apple_Inc."},
    )

    assert entity.text == "Apple"
    assert entity.label == "ORG"
    assert entity.kb_id == "https://en.wikipedia.org/wiki/Apple_Inc."
    assert entity.confidence == 0.95
    assert entity.description == "Technology company"
    assert entity.links["wikipedia"] == "https://en.wikipedia.org/wiki/Apple_Inc."


def test_fact_check_properties():
    fact_check = FactCheck(
        claim="The Earth is round",
        verification_status="VERIFIED",
        confidence=0.98,
        sources=["NASA", "Scientific American"],
        explanation="Verified through multiple scientific sources",
    )

    assert fact_check.claim == "The Earth is round"
    assert fact_check.verification_status == "VERIFIED"
    assert fact_check.confidence == 0.98
    assert "NASA" in fact_check.sources
    assert fact_check.explanation == "Verified through multiple scientific sources"


def test_error_handling(enricher):
    # Test with invalid input
    result = enricher.process_content("")
    assert result["entities"] == []
    assert result["fact_checks"] == []

    # Test with very long input
    long_text = "test " * 1000
    result = enricher.process_content(long_text)
    assert isinstance(result["entities"], list)
    assert isinstance(result["fact_checks"], list)
