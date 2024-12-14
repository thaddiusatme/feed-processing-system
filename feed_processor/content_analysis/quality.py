"""Content quality scoring system for feed content analysis."""
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from prometheus_client import Counter, Histogram

from .nlp_pipeline import NLPPipeline
from .sentiment import SentimentAnalyzer

# Metrics
QUALITY_SCORE_HISTOGRAM = Histogram(
    "content_quality_score",
    "Distribution of content quality scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
QUALITY_CHECK_ERRORS = Counter(
    "content_quality_check_errors", "Number of errors during quality checks", ["check_type"]
)


@dataclass
class QualityMetrics:
    """Container for various content quality metrics."""

    readability_score: float
    sentiment_score: float
    coherence_score: float
    engagement_score: float
    originality_score: float
    fact_density: float
    overall_score: float
    quality_flags: List[str]
    detailed_metrics: Dict[str, float]


class ContentQualityScorer:
    """Analyzes and scores content quality based on multiple dimensions."""

    def __init__(self, nlp_pipeline: NLPPipeline, sentiment_analyzer: SentimentAnalyzer):
        """Initialize the content quality scorer.

        Args:
            nlp_pipeline: NLP pipeline for text analysis
            sentiment_analyzer: Sentiment analysis component
        """
        self.nlp = nlp_pipeline
        self.sentiment = sentiment_analyzer

    def score_content(self, text: str) -> QualityMetrics:
        """Calculate comprehensive quality metrics for the given content.

        Args:
            text: The content to analyze

        Returns:
            QualityMetrics containing various quality scores and flags
        """
        try:
            # Basic text metrics
            doc = self.nlp.process(text)
            readability = self.nlp.calculate_readability(text)

            # Sentiment and emotional tone
            sentiment_results = self.sentiment.analyze_text(text)
            sentiment_score = (sentiment_results.compound_score + 1) / 2  # Normalize to 0-1

            # Coherence and structure
            coherence_score = self._calculate_coherence(doc)

            # Engagement potential
            engagement_score = self._calculate_engagement_score(doc)

            # Content originality
            originality_score = self._assess_originality(doc)

            # Fact and information density
            fact_density = self._calculate_fact_density(doc)

            # Quality flags for specific issues
            quality_flags = self._identify_quality_issues(doc)

            # Detailed metrics for transparency
            detailed_metrics = {
                "sentence_count": len(list(doc.sents)),
                "avg_sentence_length": np.mean([len(sent) for sent in doc.sents]),
                "unique_entities": len(set(ent.text for ent in doc.ents)),
                "keyword_density": len(self.nlp.extract_keywords(text)) / len(doc),
                "readability_score": readability,
                "sentiment_score": sentiment_score,
                "coherence_score": coherence_score,
                "engagement_score": engagement_score,
                "originality_score": originality_score,
                "fact_density": fact_density,
            }

            # Calculate overall score using weighted components
            overall_score = self._calculate_overall_score(detailed_metrics)

            # Record metrics
            QUALITY_SCORE_HISTOGRAM.observe(overall_score)

            return QualityMetrics(
                readability_score=readability,
                sentiment_score=sentiment_score,
                coherence_score=coherence_score,
                engagement_score=engagement_score,
                originality_score=originality_score,
                fact_density=fact_density,
                overall_score=overall_score,
                quality_flags=quality_flags,
                detailed_metrics=detailed_metrics,
            )

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="score_content").inc()
            raise RuntimeError(f"Error scoring content quality: {str(e)}") from e

    def _calculate_coherence(self, doc) -> float:
        """Calculate text coherence score based on sentence transitions and topic flow."""
        try:
            sentences = list(doc.sents)
            if len(sentences) < 2:
                return 1.0  # Single sentence is considered coherent

            # Calculate sentence similarity scores
            similarity_scores = []
            for i in range(len(sentences) - 1):
                similarity = sentences[i].similarity(sentences[i + 1])
                similarity_scores.append(similarity)

            # Calculate topic consistency
            topic_shifts = sum(1 for score in similarity_scores if score < 0.3)
            topic_consistency = 1 - (topic_shifts / len(similarity_scores))

            # Calculate overall coherence
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            coherence_score = (avg_similarity + topic_consistency) / 2

            return min(max(coherence_score, 0.0), 1.0)

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="coherence").inc()
            return 0.5  # Default to neutral score on error

    def _calculate_engagement_score(self, doc) -> float:
        """Calculate potential reader engagement based on content structure and style."""
        try:
            # Count engagement indicators
            questions = len([sent for sent in doc.sents if sent.text.strip().endswith("?")])
            exclamations = len([sent for sent in doc.sents if sent.text.strip().endswith("!")])

            # Calculate sentence variety
            sent_lengths = [len(sent) for sent in doc.sents]
            length_variance = np.var(sent_lengths) if sent_lengths else 0

            # Calculate vocabulary richness
            unique_words = len(set(token.text.lower() for token in doc if token.is_alpha))
            total_words = len([token for token in doc if token.is_alpha])
            vocabulary_richness = unique_words / total_words if total_words > 0 else 0

            # Combine factors into engagement score
            num_sentences = len(list(doc.sents))
            question_ratio = questions / num_sentences if num_sentences > 0 else 0
            exclamation_ratio = exclamations / num_sentences if num_sentences > 0 else 0

            engagement_factors = [
                vocabulary_richness * 0.4,
                min(length_variance / 100, 1.0) * 0.2,
                min((question_ratio + exclamation_ratio) * 2, 1.0) * 0.4,
            ]

            return min(max(sum(engagement_factors), 0.0), 1.0)

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="engagement").inc()
            return 0.5

    def _assess_originality(self, doc) -> float:
        """Assess content originality based on phrase uniqueness and structure."""
        try:
            # Extract significant phrases
            phrases = list(doc.noun_chunks)

            # Calculate phrase uniqueness
            unique_phrases = set(phrase.text.lower() for phrase in phrases)
            phrase_uniqueness = len(unique_phrases) / len(phrases) if phrases else 0

            # Assess sentence structure variety
            sent_structures = []
            for sent in doc.sents:
                structure = tuple(token.pos_ for token in sent)
                sent_structures.append(structure)

            unique_structures = len(set(sent_structures))
            structure_variety = unique_structures / len(sent_structures) if sent_structures else 0

            # Combine metrics
            originality_score = (phrase_uniqueness * 0.6) + (structure_variety * 0.4)

            return min(max(originality_score, 0.0), 1.0)

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="originality").inc()
            return 0.5

    def _calculate_fact_density(self, doc) -> float:
        """Calculate the density of factual information in the content."""
        try:
            # Count named entities
            named_entities = len(doc.ents)

            # Count numerical information
            numbers = len([token for token in doc if token.like_num])

            # Count fact indicators (dates, locations, organizations)
            fact_indicators = len(
                [
                    ent
                    for ent in doc.ents
                    if ent.label_ in ["DATE", "GPE", "ORG", "MONEY", "PERCENT"]
                ]
            )

            # Calculate density relative to content length
            total_tokens = len(doc)
            if total_tokens == 0:
                return 0.0

            fact_score = (named_entities + numbers + fact_indicators) / total_tokens
            normalized_score = min(fact_score * 3, 1.0)  # Scale up but cap at 1.0

            return normalized_score

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="fact_density").inc()
            return 0.5

    def _identify_quality_issues(self, doc) -> List[str]:
        """Identify potential quality issues in the content."""
        issues = []

        try:
            # Check for excessive repetition
            word_freq = {}
            for token in doc:
                if token.is_alpha and not token.is_stop:
                    word_freq[token.lower_] = word_freq.get(token.lower_, 0) + 1

            max_freq = max(word_freq.values()) if word_freq else 0
            if max_freq > len(doc) * 0.1:  # More than 10% repetition
                issues.append("excessive_repetition")

            # Check sentence length variation
            sent_lengths = [len(sent) for sent in doc.sents]
            if sent_lengths:
                avg_length = sum(sent_lengths) / len(sent_lengths)
                if avg_length > 40:
                    issues.append("long_sentences")
                elif avg_length < 10:
                    issues.append("short_sentences")

            # Check content length
            if len(doc) < 100:
                issues.append("insufficient_length")

            # Check readability issues
            if self.nlp.calculate_readability(doc.text) < 0.3:
                issues.append("low_readability")

            # Check sentiment extremes
            sentiment_results = self.sentiment.analyze_text(doc.text)
            if abs(sentiment_results.compound_score) > 0.8:
                issues.append("extreme_sentiment")

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="quality_issues").inc()

        return issues

    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall quality score from individual metrics."""
        try:
            weights = {
                "readability_score": 0.2,
                "coherence_score": 0.2,
                "engagement_score": 0.15,
                "originality_score": 0.15,
                "fact_density": 0.15,
                "sentiment_score": 0.15,
            }

            weighted_sum = sum(
                metrics[key] * weight for key, weight in weights.items() if key in metrics
            )

            return min(max(weighted_sum, 0.0), 1.0)

        except Exception as e:
            QUALITY_CHECK_ERRORS.labels(check_type="overall_score").inc()
            return 0.5
