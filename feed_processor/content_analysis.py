"""Content analysis module for feed processing system."""

import re
from typing import List


class ReadabilityAnalyzer:
    """Analyzes text readability using various metrics."""

    def __init__(self):
        self.vowels = set("aeiouy")

    def calculate_flesch_kincaid_score(self, text: str) -> float:
        """
        Calculate the Flesch-Kincaid readability score.
        Score ranges from 0 (very difficult) to 100 (very easy).
        """
        if not text:
            return 0.0

        # Clean and prepare text
        text = self._clean_text(text)

        # Count basic metrics
        word_count = len(text.split())
        if word_count == 0:
            return 0.0

        sentence_count = self._count_sentences(text)
        if sentence_count == 0:
            return 0.0

        syllable_count = sum(self._count_syllables(word) for word in text.split())

        # Calculate Flesch-Kincaid score
        score = (
            206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
        )

        # Clamp score between 0 and 100
        return max(0.0, min(100.0, score))

    def _clean_text(self, text: str) -> str:
        """Remove special characters and normalize text."""
        # Remove numbers and special characters, keeping periods for sentence counting
        text = re.sub(r"[^a-zA-Z\s\.]", "", text)
        return text.strip()

    def _count_syllables(self, word: str) -> int:
        """Count the number of syllables in a word."""
        word = word.lower()
        count = 0
        prev_is_vowel = False

        for char in word:
            is_vowel = char in self.vowels
            if is_vowel and not prev_is_vowel:
                count += 1
            prev_is_vowel = is_vowel

        # Handle special cases
        if word.endswith("e"):
            count -= 1
        if word.endswith("le") and len(word) > 2 and word[-3] not in self.vowels:
            count += 1
        if count == 0:
            count = 1

        return count

    def _count_sentences(self, text: str) -> int:
        """Count the number of sentences in text."""
        # Split on period, exclamation mark, or question mark
        sentences = re.split(r"[.!?]+", text)
        # Filter out empty strings
        return len([s for s in sentences if s.strip()])
