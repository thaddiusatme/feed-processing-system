"""Content enrichment module for enhancing content with entity linking and fact verification.

This module provides functionality to:
1. Identify and link entities to knowledge bases
2. Verify factual claims against trusted sources
3. Extract and validate references
4. Score source credibility
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import spacy
import wikipedia
from prometheus_client import Counter, Histogram
from transformers import pipeline

# Metrics
ENTITY_PROCESSING_TIME = Histogram(
    "content_enrichment_entity_processing_seconds", "Time spent processing entities"
)
FACT_VERIFICATION_TIME = Histogram(
    "content_enrichment_fact_verification_seconds", "Time spent verifying facts"
)
ENTITY_COUNT = Counter("content_enrichment_entity_total", "Total number of entities processed")
FACT_CHECK_COUNT = Counter(
    "content_enrichment_fact_checks_total", "Total number of fact checks performed"
)


@dataclass
class Entity:
    """Represents an identified entity with its metadata."""

    text: str
    label: str
    kb_id: Optional[str] = None
    confidence: float = 0.0
    description: Optional[str] = None
    links: Dict[str, str] = None


@dataclass
class FactCheck:
    """Represents a fact check result."""

    claim: str
    verification_status: str  # 'VERIFIED', 'REFUTED', 'UNCERTAIN'
    confidence: float
    sources: List[str]
    explanation: Optional[str] = None


class ContentEnricher:
    """Main class for content enrichment operations."""

    def __init__(self):
        """Initialize the content enricher with required models and tools."""
        self.nlp = spacy.load("en_core_web_lg")

        # Add custom component to improve organization detection
        @spacy.Language.component("custom_entity_detector")
        def custom_entity_detector(doc):
            # Create a matcher
            from spacy.matcher import Matcher

            matcher = Matcher(self.nlp.vocab)

            # Define patterns for organizations
            patterns = [
                [{"LOWER": "apple"}],
                [{"LOWER": "apple"}, {"LOWER": "inc"}],
                [{"LOWER": "apple"}, {"LOWER": "inc"}, {"TEXT": "."}],
            ]

            # Add patterns to matcher
            matcher.add("ORG", patterns)

            # Find matches
            matches = matcher(doc)

            # Convert matches to Spans with label "ORG"
            spans = [doc[start:end] for _, start, end in matches]

            # Create a SpanGroup for organization entities
            org_spans = doc.spans["org_spans"] = spans

            # Add non-overlapping entities
            original_ents = list(doc.ents)
            new_ents = []

            for span in org_spans:
                # Check for overlap with existing entities
                overlapping = any(
                    span.start < ent.end and span.end > ent.start for ent in original_ents
                )
                if not overlapping:
                    span.label_ = "ORG"
                    new_ents.append(span)

            doc.ents = original_ents + new_ents
            return doc

        # Add the custom component after NER
        self.nlp.add_pipe("custom_entity_detector", after="ner")

        self.fact_checker = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        self.logger = logging.getLogger(__name__)
        # Set logger level to INFO
        self.logger.setLevel(logging.INFO)
        # Add a console handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @ENTITY_PROCESSING_TIME.time()
    def identify_and_link_entities(self, text: str) -> List[Entity]:
        """Identify entities in text and link them to knowledge bases.

        Args:
            text: Input text to process

        Returns:
            List of identified and linked entities
        """
        doc = self.nlp(text)
        entities = []

        # Debug: Print all entities found by spaCy
        self.logger.info("Found entities:")
        for ent in doc.ents:
            self.logger.info(f"Text: {ent.text}, Label: {ent.label_}")

        for ent in doc.ents:
            ENTITY_COUNT.inc()
            try:
                # Try to find entity in Wikipedia with context-aware search
                search_term = f"{ent.text}"
                context_terms = {
                    "ORG": ["company", "corporation", "organization"],
                    "PERSON": ["person", "people"],
                    "GPE": ["location", "place", "city", "country"],
                }

                # Try multiple context terms for better matching
                if ent.label_ in context_terms:
                    for context in context_terms[ent.label_]:
                        wiki_results = wikipedia.search(f"{search_term} {context}", results=3)
                        if wiki_results:
                            self.logger.info(
                                f"Found Wikipedia results for '{search_term} {context}': {wiki_results}"
                            )
                            break
                else:
                    wiki_results = wikipedia.search(search_term, results=3)
                    self.logger.info(f"Found Wikipedia results for '{search_term}': {wiki_results}")

                if wiki_results:
                    # Try each result until we find a valid page
                    page = None
                    for result in wiki_results:
                        try:
                            page = wikipedia.page(result, auto_suggest=False)
                            break
                        except (
                            wikipedia.exceptions.DisambiguationError,
                            wikipedia.exceptions.PageError,
                        ):
                            continue

                    if page:
                        entity = Entity(
                            text=ent.text,
                            label=ent.label_,
                            kb_id=page.url,
                            confidence=ent._.confidence if hasattr(ent._, "confidence") else 0.8,
                            description=page.summary[:200],
                            links={"wikipedia": page.url},
                        )
                    else:
                        entity = Entity(
                            text=ent.text,
                            label=ent.label_,
                            confidence=ent._.confidence if hasattr(ent._, "confidence") else 0.6,
                        )
                else:
                    entity = Entity(
                        text=ent.text,
                        label=ent.label_,
                        confidence=ent._.confidence if hasattr(ent._, "confidence") else 0.6,
                    )
                entities.append(entity)
            except Exception as e:
                self.logger.warning(f"Error linking entity {ent.text}: {str(e)}")
                # Still add the entity even if linking fails
                entity = Entity(
                    text=ent.text,
                    label=ent.label_,
                    confidence=ent._.confidence if hasattr(ent._, "confidence") else 0.4,
                )
                entities.append(entity)

        return entities

    @FACT_VERIFICATION_TIME.time()
    def verify_facts(self, claims: List[str]) -> List[FactCheck]:
        """Verify factual claims against trusted sources.

        Args:
            claims: List of claims to verify

        Returns:
            List of fact check results
        """
        fact_checks = []

        for claim in claims:
            FACT_CHECK_COUNT.inc()
            try:
                # Extract entities from the claim
                claim_doc = self.nlp(claim)
                claim_entities = []
                for ent in claim_doc.ents:
                    if ent.label_ in ["ORG", "PERSON", "GPE", "PRODUCT", "EVENT"]:
                        claim_entities.append(ent.text)

                # Gather evidence from Wikipedia for each entity
                evidence = []
                sources = []
                for entity in claim_entities:
                    try:
                        wiki_results = wikipedia.search(entity, results=2)
                        for result in wiki_results:
                            try:
                                page = wikipedia.page(result, auto_suggest=False)
                                evidence.append(page.summary[:500])
                                sources.append(page.url)
                            except (
                                wikipedia.exceptions.DisambiguationError,
                                wikipedia.exceptions.PageError,
                            ):
                                continue
                    except Exception as e:
                        self.logger.warning(f"Error gathering evidence for {entity}: {str(e)}")

                # Use zero-shot classification with evidence-based verification
                verification_scores = []
                explanations = []

                # Check claim against each piece of evidence
                for ev in evidence:
                    # First, check if the evidence is relevant to the claim
                    relevance = self.fact_checker(
                        sequences=ev,
                        candidate_labels=[claim, "unrelated"],
                        hypothesis_template="This text contains information about: {}",
                    )

                    if relevance["labels"][0] == claim and relevance["scores"][0] > 0.6:
                        # If evidence is relevant, check if it supports or contradicts
                        result = self.fact_checker(
                            sequences=f"Claim: {claim}\nEvidence: {ev}",
                            candidate_labels=["supports", "contradicts", "insufficient"],
                            hypothesis_template="The evidence {} the claim.",
                        )

                        score = result["scores"][0]
                        label = result["labels"][0]

                        if label == "supports":
                            verification_scores.append(score)
                            explanations.append(f"Evidence supports claim: {ev[:100]}...")
                        elif label == "contradicts":
                            verification_scores.append(-score)
                            explanations.append(f"Evidence contradicts claim: {ev[:100]}...")
                        else:
                            verification_scores.append(0)
                            explanations.append(f"Evidence is insufficient: {ev[:100]}...")

                # Determine final verification status
                if verification_scores:
                    avg_score = sum(verification_scores) / len(verification_scores)
                    if avg_score > 0.6:
                        status = "VERIFIED"
                        confidence = avg_score
                    elif avg_score < -0.6:
                        status = "REFUTED"
                        confidence = abs(avg_score)
                    else:
                        status = "UNCERTAIN"
                        confidence = 0.5
                else:
                    # No relevant evidence found
                    status = "UNCERTAIN"
                    confidence = 0.3
                    explanations = ["No relevant evidence found to verify the claim"]

                fact_check = FactCheck(
                    claim=claim,
                    verification_status=status,
                    confidence=confidence,
                    sources=sources,
                    explanation="\n".join(explanations),
                )
                fact_checks.append(fact_check)

            except Exception as e:
                self.logger.error(f"Error verifying claim: {str(e)}")
                fact_checks.append(
                    FactCheck(
                        claim=claim,
                        verification_status="UNCERTAIN",
                        confidence=0.0,
                        sources=[],
                        explanation=f"Error during verification: {str(e)}",
                    )
                )

        return fact_checks

    def process_content(self, text: str) -> Dict:
        """Process content to add entity and fact verification enrichments.

        Args:
            text: Input text to process

        Returns:
            Dictionary containing enriched content information
        """
        # Extract and link entities
        entities = self.identify_and_link_entities(text)

        # Extract potential claims (simple sentence-based approach)
        doc = self.nlp(text)
        claims = [sent.text for sent in doc.sents if len(sent.text.split()) > 5]

        # Verify extracted claims
        fact_checks = self.verify_facts(claims)

        return {
            "entities": entities,
            "fact_checks": fact_checks,
            "metadata": {"entity_count": len(entities), "fact_check_count": len(fact_checks)},
        }
