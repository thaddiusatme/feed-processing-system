"""Advanced summarization features for content enhancement pipeline.

This module implements advanced summarization capabilities including:
- Multi-document summarization
- Cross-reference analysis
- Topic-based summarization
- Temporal summarization
- Update summarization
"""

import logging
from typing import Dict, List, Optional

import numpy as np
from prometheus_client import Counter, Histogram
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline

from feed_processor.content_analysis.summarization import ContentSummarizer, SummarizationResult

logger = logging.getLogger(__name__)

# Metrics
advanced_summarization_time = Histogram(
    "advanced_summarization_processing_seconds",
    "Time spent processing advanced summarization",
    ["operation"],
)
advanced_summarization_errors = Counter(
    "advanced_summarization_errors_total",
    "Number of errors in advanced summarization",
    ["error_type"],
)


class AdvancedSummarizer:
    """Advanced summarization capabilities building on base ContentSummarizer."""

    def __init__(
        self,
        base_summarizer: ContentSummarizer,
        multi_doc_model: str = "facebook/bart-large-xsum",
        similarity_threshold: float = 0.5,
        mock_pipeline=None,
    ):
        """Initialize advanced summarizer.

        Args:
            base_summarizer: Base ContentSummarizer instance
            multi_doc_model: Model for multi-document summarization
            similarity_threshold: Threshold for content similarity
            mock_pipeline: Optional mock pipeline for testing
        """
        self.base_summarizer = base_summarizer
        self.similarity_threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(stop_words="english")

        if mock_pipeline:
            self.multi_doc_pipeline = lambda text, max_length=None, min_length=None: [
                {"summary_text": mock_pipeline(text)}
            ]
        else:
            self.multi_doc_pipeline = pipeline(
                "summarization",
                model=multi_doc_model,
                tokenizer=multi_doc_model,
            )

    @advanced_summarization_time.labels(operation="multi_doc").time()
    def multi_document_summarize(
        self, documents: List[str], metadata: Optional[List[Dict]] = None
    ) -> SummarizationResult:
        """Generate a summary across multiple related documents.

        Args:
            documents: List of document texts to summarize
            metadata: Optional metadata for each document

        Returns:
            SummarizationResult containing combined and individual summaries

        Raises:
            ValueError: If documents list is empty
        """
        if not documents:
            raise ValueError("Documents list cannot be empty")

        try:
            # Generate individual summaries
            doc_summaries = [self.base_summarizer.summarize(doc) for doc in documents]

            # Find common themes using TF-IDF
            tfidf_matrix = self.vectorizer.fit_transform(documents)
            feature_names = np.array(self.vectorizer.get_feature_names_out())
            common_themes = self._extract_common_themes(tfidf_matrix, feature_names)

            # Generate cross-references
            cross_refs = self._generate_cross_references(documents, doc_summaries)

            # Create timeline if metadata contains dates
            timeline = None
            if metadata and all("date" in meta for meta in metadata):
                timeline = self._create_timeline(doc_summaries, metadata)

            # Generate combined summary
            combined_text = " ".join(summary.abstractive_summary for summary in doc_summaries)
            combined_summary = self.multi_doc_pipeline(
                combined_text,
                max_length=self.base_summarizer.max_length * 2,
                min_length=self.base_summarizer.min_length,
            )[0]["summary_text"]

            return SummarizationResult(
                extractive_summary=combined_summary,
                abstractive_summary=combined_summary,
                key_points=self._extract_key_points(doc_summaries),
                summary_length=len(combined_summary),
                compression_ratio=len(combined_summary) / sum(len(doc) for doc in documents),
                confidence_score=np.mean([s.confidence_score for s in doc_summaries]),
                metadata={
                    "num_documents": len(documents),
                    "common_themes": common_themes,
                },
                common_themes=common_themes,
                document_summaries=doc_summaries,
                cross_references=cross_refs,
                timeline=timeline,
            )

        except Exception as e:
            logger.error(f"Error in multi-document summarization: {str(e)}")
            advanced_summarization_errors.labels(error_type="multi_doc").inc()
            raise

    def _extract_common_themes(
        self, tfidf_matrix: np.ndarray, feature_names: np.ndarray, num_themes: int = 5
    ) -> List[str]:
        """Extract common themes from TF-IDF matrix.

        Args:
            tfidf_matrix: Document-term matrix
            feature_names: Array of term names
            num_themes: Number of themes to extract

        Returns:
            List of common themes
        """
        # Get average TF-IDF scores across documents
        avg_scores = np.mean(tfidf_matrix.toarray(), axis=0)
        top_indices = np.argsort(avg_scores)[-num_themes:]
        return feature_names[top_indices].tolist()

    def _generate_cross_references(
        self, documents: List[str], summaries: List[SummarizationResult]
    ) -> List[Dict[str, str]]:
        """Generate cross-references between documents.

        Args:
            documents: Original document texts
            summaries: Generated summaries for each document

        Returns:
            List of cross-reference information
        """
        cross_refs = []
        for i, (doc1, sum1) in enumerate(zip(documents, summaries)):
            for j, (doc2, sum2) in enumerate(zip(documents, summaries)):
                if i != j:
                    similarity = self._calculate_similarity(
                        sum1.abstractive_summary, sum2.abstractive_summary
                    )
                    if similarity > self.similarity_threshold:
                        cross_refs.append(
                            {
                                "source_idx": i,
                                "target_idx": j,
                                "similarity": similarity,
                                "shared_topics": list(set(sum1.key_points) & set(sum2.key_points)),
                            }
                        )
        return cross_refs

    def _create_timeline(
        self, summaries: List[SummarizationResult], metadata: List[Dict]
    ) -> List[Dict]:
        """Create a timeline of events from document summaries.

        Args:
            summaries: List of document summaries
            metadata: Metadata for each document containing dates

        Returns:
            List of timeline entries
        """
        timeline = []
        for summary, meta in zip(summaries, metadata):
            if "date" in meta:
                timeline.append(
                    {
                        "date": meta["date"],
                        "summary": summary.abstractive_summary,
                        "key_points": summary.key_points,
                    }
                )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    def _extract_key_points(self, summaries: List[SummarizationResult]) -> List[str]:
        """Extract key points from multiple summaries.

        Args:
            summaries: List of document summaries

        Returns:
            Combined and deduplicated list of key points
        """
        all_points = []
        for summary in summaries:
            all_points.extend(summary.key_points)

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in all_points if not (x in seen or seen.add(x))]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using TF-IDF.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0 and 1
        """
        # Create a new vectorizer for each comparison to ensure consistent vocabulary
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf = vectorizer.fit_transform([text1, text2])
        # Normalize the similarity score to be between 0 and 1
        similarity = (tfidf * tfidf.T).toarray()[0, 1]
        return min(1.0, max(0.0, similarity))
