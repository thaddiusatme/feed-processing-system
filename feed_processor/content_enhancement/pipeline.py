"""Content enhancement pipeline module.

This module provides the core pipeline for enhancing content items with
additional information such as summaries, key facts, and quality metrics.
The pipeline processes content through multiple stages of analysis and
enhancement.
"""

import logging
from typing import Dict, List, Optional

from fuzzywuzzy import fuzz, process

from feed_processor.storage.models import ContentItem

logger = logging.getLogger(__name__)


class ContentEnhancementPipeline:
    """Pipeline for enhancing content items with additional information.

    This pipeline processes content items to:
    - Generate summaries
    - Extract key facts and entities
    - Calculate quality metrics
    - Apply content filters
    """

    def __init__(self, min_content_length: int = 100):
        """Initialize the content enhancement pipeline.

        Args:
            min_content_length: Minimum content length to process
        """
        self.min_content_length = min_content_length

    async def process_item(self, item: ContentItem) -> Optional[Dict]:
        """Process a single content item through the enhancement pipeline.

        Performs the full pipeline processing on a single content item,
        including validation, summarization, fact extraction, and quality scoring.

        Args:
            item: Content item to process

        Returns:
            Enhanced content data or None if processing fails
        """
        try:
            if not self._validate_content(item):
                logger.warning(f"Content validation failed for item {item.id}")
                return None

            summary = await self._generate_summary(item.content)
            facts = await self._extract_facts(item.content)
            quality_score = self._calculate_quality_score(item, summary, facts)

            return {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "summary": summary,
                "facts": facts,
                "quality_score": quality_score,
                "content_type": item.content_type,
                "metadata": {
                    **item.metadata,
                    "quality_score": quality_score,
                    "has_summary": bool(summary),
                    "fact_count": len(facts),
                },
            }

        except Exception as e:
            logger.error(f"Error processing item {item.id}: {str(e)}")
            return None

    def _validate_content(self, item: ContentItem) -> bool:
        """Validate content item before processing.

        Performs basic validation checks on the content item to ensure it meets
        minimum requirements for processing.

        Args:
            item: Content item to validate

        Returns:
            True if content is valid, False otherwise
        """
        if not item.content:
            logger.warning(f"Empty content for item {item.id}")
            return False

        if len(item.content) < self.min_content_length:
            logger.warning(f"Content too short for item {item.id}: {len(item.content)} chars")
            return False

        return True

    async def _generate_summary(self, content: str) -> str:
        """Generate a summary of the content.

        Creates a concise summary of the content, typically by extracting the
        most important information or key points.

        Args:
            content: Text content to summarize

        Returns:
            Generated summary
        """
        # Placeholder for actual summarization logic
        # This would typically use an NLP service or library
        if len(content) <= 200:
            return content

        return content[:200] + "..."

    async def _extract_facts(self, content: str) -> List[Dict]:
        """Extract key facts from content.

        Analyzes the content to identify and extract key facts, entities, or
        other relevant information.

        Args:
            content: Text content to analyze

        Returns:
            List of extracted facts
        """
        # Placeholder for actual fact extraction logic
        # This would typically use an NLP service or library
        return []

    def _calculate_quality_score(self, item: ContentItem, summary: str, facts: List[Dict]) -> float:
        """Calculate quality score for content item.

        Evaluates the quality of the content item based on various factors such
        as content length, summary quality, and fact extraction.

        Args:
            item: Original content item
            summary: Generated summary
            facts: Extracted facts

        Returns:
            Quality score between 0 and 1
        """
        # Simple scoring based on content length and extracted information
        score = 0.0

        # Length score (30%)
        length_score = min(1.0, len(item.content) / 1000)
        score += 0.3 * length_score

        # Summary score (40%)
        summary_score = 1.0 if summary else 0.0
        score += 0.4 * summary_score

        # Facts score (30%)
        facts_score = min(1.0, len(facts) / 5)
        score += 0.3 * facts_score

        return round(score, 2)

    def _find_source_context(self, fact: str, content: str) -> Optional[str]:
        """Find the context in the source content where a fact appears.

        Searches for the fact in the original content and returns the surrounding
        context if found.

        Args:
            fact: Fact to find in the content
            content: Original content to search

        Returns:
            Context where the fact appears or None if not found
        """
        try:
            # First try exact match
            if fact in content:
                start = content.index(fact)
                end = start + len(fact)
                return content[max(0, start - 50) : min(len(content), end + 50)]

            # Try fuzzy matching if exact match fails
            matches = process.extract(fact, [content], scorer=fuzz.token_sort_ratio)
            if matches and matches[0][1] > 80:  # If similarity > 80%
                return matches[0][0]

            return None
        except (IndexError, TypeError) as e:
            logger.error(f"Error finding source context: {e}")
            return None

    def _calculate_readability_score(self, text: str) -> float:
        """Calculate readability score using various metrics.

        Evaluates the readability of the text based on factors such as word and
        sentence length.

        Args:
            text: Text to evaluate

        Returns:
            Readability score between 0 and 1
        """
        try:
            if not text:
                return 0.0

            # Basic metrics
            words = text.split()
            sentences = text.split(".")
            avg_word_length = sum(len(word) for word in words) / len(words)
            avg_sentence_length = len(words) / len(sentences)

            # Penalize very long sentences and words
            length_penalty = max(0, (avg_sentence_length - 20) / 20)
            word_penalty = max(0, (avg_word_length - 6) / 4)

            base_score = 1.0 - (length_penalty + word_penalty) / 2
            return max(0.0, min(1.0, base_score))

        except (ZeroDivisionError, TypeError) as e:
            logger.error(f"Error calculating readability score: {e}")
            return 0.8  # Default score on error
