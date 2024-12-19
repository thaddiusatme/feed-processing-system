"""Topic analysis module for extracting and analyzing topics from documents."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import nltk
import numpy as np
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import sent_tokenize, word_tokenize
from prometheus_client import Counter as PrometheusCounter
from prometheus_client import Histogram
from rake_nltk import Rake
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")

try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet")

try:
    nltk.data.find("taggers/averaged_perceptron_tagger")
except LookupError:
    nltk.download("averaged_perceptron_tagger")

# Metrics
topic_processing_time = Histogram(
    "topic_processing_seconds", "Time spent processing topics", ["operation"]
)

topic_count = PrometheusCounter("topics_extracted_total", "Total number of topics extracted")


@dataclass
class ProcessedText:
    """Processed text with NLP annotations."""

    tokens: List[str]
    sentences: List[str]
    lemmas: List[str]
    pos_tags: List[Tuple[str, str]]


@dataclass
class Topic:
    """Represents a topic extracted from documents."""

    name: str
    keywords: List[str]
    document_count: int
    confidence: float

    def __eq__(self, other) -> bool:
        """Compare topics for equality."""
        if not isinstance(other, Topic):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        """Hash based on topic name."""
        return hash(self.name)


@dataclass
class TopicAnalysisResult:
    """Results from topic analysis."""

    topics: List[Topic] = None
    document_topics: Dict[Union[int, str], List[Tuple[Topic, float]]] = None
    emerging_topics: List[Topic] = None
    related_topics: Dict[str, List[Topic]] = None
    topic_coherence: float = 0.0

    def __post_init__(self):
        """Initialize default values."""
        self.topics = self.topics or []
        self.document_topics = self.document_topics or {}
        self.emerging_topics = self.emerging_topics or []
        self.related_topics = self.related_topics or {}


class NLP:
    """NLP processing utilities."""

    def __init__(self):
        """Initialize NLP components."""
        self.stop_words = set(stopwords.words("english"))
        self.lemmatizer = WordNetLemmatizer()

    def word_tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        return word_tokenize(text)

    def sent_tokenize(self, text: str) -> List[str]:
        """Tokenize text into sentences."""
        return sent_tokenize(text)

    def process_text(self, text: str) -> ProcessedText:
        """Process text with NLP annotations."""
        # Tokenize
        tokens = self.word_tokenize(text.lower())
        sentences = self.sent_tokenize(text)

        # Remove stopwords and lemmatize
        tokens = [t for t in tokens if t.isalnum() and t not in self.stop_words]
        lemmas = [self.lemmatizer.lemmatize(t) for t in tokens]

        # POS tagging
        pos_tags = nltk.pos_tag(tokens)

        return ProcessedText(tokens=tokens, sentences=sentences, lemmas=lemmas, pos_tags=pos_tags)


class TopicAnalyzer:
    """Topic analysis system."""

    def __init__(self):
        """Initialize the topic analyzer."""
        self.nlp = NLP()
        self.vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2)
        )
        self.rake = Rake()

    def analyze(
        self, documents: List[str], min_topic_size: int = 2, min_cooccurrence: float = 0.3
    ) -> TopicAnalysisResult:
        """Analyze topics in documents."""
        try:
            # Extract initial topics
            topics = self._extract_topics(documents)
            if not topics:
                return TopicAnalysisResult()

            # Assign documents to topics
            document_topics = {}
            for doc_id, doc in enumerate(documents):
                # Calculate similarity scores between document and topics
                doc_scores = []
                doc_tokens = set(word_tokenize(doc.lower()))

                for topic in topics:
                    # Calculate overlap between document terms and topic keywords
                    topic_terms = set(topic.keywords)
                    overlap = len(doc_tokens & topic_terms)
                    if overlap > 0:
                        # Calculate similarity score
                        similarity = overlap / (len(topic_terms) + len(doc_tokens) - overlap)
                        doc_scores.append((topic, similarity))

                # Sort by similarity and keep scores above threshold
                doc_scores.sort(key=lambda x: x[1], reverse=True)
                significant_topics = [(t, s) for t, s in doc_scores if s >= 0.2]
                if significant_topics:
                    document_topics[doc_id] = significant_topics

            # Detect emerging topics
            emerging_topics = self._detect_emerging_topics(topics, document_topics)

            # Find related topics
            related_topics = self._find_related_topics(topics, document_topics)

            # Calculate topic coherence
            coherence = self._calculate_topic_coherence(topics, document_topics)

            return TopicAnalysisResult(
                topics=topics,
                document_topics=document_topics,
                emerging_topics=emerging_topics,
                related_topics=related_topics,
                topic_coherence=coherence,
            )

        except Exception as e:
            logger.error(f"Error in topic analysis: {str(e)}")
            return TopicAnalysisResult()

    @topic_processing_time.labels(operation="extract_topics").time()
    def extract_topics(
        self,
        documents: List[Union[str, Dict[str, str]]],
        min_cluster_size: int = 2,
    ) -> TopicAnalysisResult:
        """Extract topics from a collection of documents.

        Args:
            documents: List of strings or dictionaries containing 'id' and 'text' keys
            min_cluster_size: Minimum number of documents to form a topic cluster
        """
        # Handle both string and dictionary formats
        doc_texts = []
        doc_ids = []

        for i, doc in enumerate(documents):
            if isinstance(doc, dict):
                doc_texts.append(doc["text"])
                doc_ids.append(doc["id"])
            else:
                doc_texts.append(doc)
                doc_ids.append(str(i))

        result = self._extract_topics(doc_texts, min_cluster_size)

        # Update document_topics with document IDs
        updated_doc_topics = {}
        for i, doc_id in enumerate(doc_ids):
            if i in result.document_topics:
                updated_doc_topics[doc_id] = result.document_topics[i]
        result.document_topics = updated_doc_topics

        return result

    def _extract_topics(
        self, documents: List[str], min_cluster_size: int = 2
    ) -> TopicAnalysisResult:
        """Extract topics using TF-IDF and DBSCAN clustering."""
        if not documents:
            return TopicAnalysisResult()

        # Process documents
        processed_docs = []
        for doc in documents:
            processed = self.nlp.process_text(doc)
            # Use both lemmas and original tokens for better matching
            processed_text = " ".join(processed.lemmas + [t.lower() for t in processed.tokens])
            processed_docs.append(processed_text)

        # Vectorize documents
        try:
            self.vectorizer = TfidfVectorizer(
                max_features=100,  # Reduced for small document sets
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,  # Allow terms that appear in just one document
                max_df=0.9,  # Filter out terms that appear in >90% of docs
            )
            tfidf_matrix = self.vectorizer.fit_transform(processed_docs)
        except ValueError:
            # Handle empty documents
            return TopicAnalysisResult()

        # Always use custom clustering for small document sets to ensure multiple topics
        # Simple clustering based on document similarity
        num_clusters = max(2, len(documents) // 2)
        centers = []
        labels = []
        doc_vectors = tfidf_matrix.toarray()

        # Initialize first center
        centers.append(doc_vectors[0])
        labels.append(0)

        # Assign remaining documents
        for i in range(1, len(doc_vectors)):
            doc_vector = doc_vectors[i]

            # Find similarities to existing centers
            similarities = [
                np.dot(doc_vector, center) / (np.linalg.norm(doc_vector) * np.linalg.norm(center))
                for center in centers
            ]

            # Create new cluster if document is sufficiently different
            if (
                not similarities or max(similarities) < 0.5
            ):  # Lower threshold to create more clusters
                if len(centers) < num_clusters:
                    centers.append(doc_vector)
                    labels.append(len(centers) - 1)
                    continue

            # Assign to most similar cluster
            closest = np.argmax(similarities)
            labels.append(closest)

        # Convert to numpy array for compatibility
        labels = np.array(labels)
        unique_labels = set(labels)

        # Extract topics from clusters
        topics = []
        document_topics = {}

        # Get feature names
        feature_names = self.vectorizer.get_feature_names_out()

        for label in unique_labels:
            # Get documents in cluster
            cluster_docs = np.where(labels == label)[0]

            # Get top terms for cluster using TF-IDF scores
            cluster_center = doc_vectors[cluster_docs].mean(axis=0)
            top_term_indices = cluster_center.argsort()[-10:][::-1]  # Get top 10 terms
            keywords = [feature_names[i] for i in top_term_indices]

            # Filter out single-character keywords and duplicates
            keywords = [k for k in keywords if len(k) > 1]
            keywords = list(dict.fromkeys(keywords))  # Remove duplicates while preserving order

            # Create topic
            topic_name = " + ".join(keywords[:3])  # More descriptive topic names
            topic = Topic(
                name=topic_name,
                keywords=keywords,
                document_count=len(cluster_docs),
                confidence=min(1.0, len(cluster_docs) / len(documents)),
            )
            topics.append(topic)

            # Assign documents to topic with improved scoring
            for doc_idx in cluster_docs:
                doc_vector = doc_vectors[doc_idx]
                # Use cosine similarity for topic assignment
                topic_score = float(
                    np.dot(doc_vector, cluster_center)
                    / (np.linalg.norm(doc_vector) * np.linalg.norm(cluster_center))
                )

                if doc_idx not in document_topics:
                    document_topics[doc_idx] = []
                document_topics[doc_idx].append((topic, topic_score))

        # Sort topics by document count and confidence
        topics.sort(key=lambda x: (x.document_count, x.confidence), reverse=True)

        # Find emerging topics with improved detection
        emerging_topics = self._detect_emerging_topics(topics, document_topics)

        # Find related topics
        related_topics = self._find_related_topics(topics, document_topics)

        # Calculate topic coherence
        topic_coherence = self._calculate_topic_coherence(topics, document_topics)

        return TopicAnalysisResult(
            topics=topics,
            document_topics=document_topics,
            emerging_topics=emerging_topics,
            related_topics=related_topics,
            topic_coherence=topic_coherence,
        )

    def _find_related_topics(
        self, topics: List[Topic], document_topics: Dict[int, List[Tuple[Topic, float]]]
    ) -> Dict[str, List[Topic]]:
        """Find related topics based on co-occurrence and keyword similarity."""
        if len(topics) < 2:
            return {}

        # Calculate keyword similarity between topics
        topic_similarity = defaultdict(dict)
        for t1 in topics:
            for t2 in topics:
                if t1 != t2:
                    # Calculate both exact and partial keyword matches
                    t1_keywords = set(t1.keywords)
                    t2_keywords = set(t2.keywords)

                    # Exact matches (Jaccard similarity)
                    intersection = len(t1_keywords & t2_keywords)
                    union = len(t1_keywords | t2_keywords)
                    exact_sim = intersection / union if union > 0 else 0

                    # Partial matches (substring matching)
                    partial_matches = 0
                    for k1 in t1_keywords:
                        for k2 in t2_keywords:
                            # Check both directions
                            if k1 in k2 or k2 in k1:
                                partial_matches += 1
                    max_possible = len(t1_keywords) + len(t2_keywords)
                    partial_sim = partial_matches / max_possible if max_possible > 0 else 0

                    # Combined similarity score
                    topic_similarity[t1][t2] = (exact_sim + partial_sim) / 2

        # Find related topics based on similarity
        related_topics = {}
        for topic in topics:
            # Get topics with similarity above threshold
            similar_topics = []
            for other in topics:
                if topic != other:
                    similarity = topic_similarity[topic][other]
                    if similarity > 0.1:  # Lower threshold to find more relationships
                        similar_topics.append(other)

            if similar_topics:
                related_topics[topic.name] = similar_topics

        return related_topics

    def _detect_emerging_topics(
        self, topics: List[Topic], document_topics: Dict[int, List[Tuple[Topic, float]]]
    ) -> List[Topic]:
        """Detect emerging topics based on document distribution."""
        if not topics or not document_topics:
            return []

        # Get temporal distribution of documents
        doc_ids = sorted(document_topics.keys())
        if len(doc_ids) < 2:  # Need at least 2 documents to detect trends
            return []

        # Split documents into time periods (using more granular periods)
        num_periods = min(3, len(doc_ids))  # Use up to 3 periods for better trend detection
        period_size = max(1, len(doc_ids) // num_periods)
        periods = [doc_ids[i : i + period_size] for i in range(0, len(doc_ids), period_size)]

        # Calculate topic frequencies and growth rates per period
        topic_frequencies = defaultdict(lambda: [0] * len(periods))
        topic_doc_counts = defaultdict(lambda: [0] * len(periods))

        # Count document occurrences for each topic in each period
        for period_idx, period_docs in enumerate(periods):
            for doc_id in period_docs:
                if doc_id in document_topics:
                    for topic, score in document_topics[doc_id]:
                        if score >= 0.2:  # Lower threshold for small sets
                            topic_frequencies[topic][period_idx] += score
                            topic_doc_counts[topic][period_idx] += 1

        # Identify emerging topics based on growth rate and minimum presence
        emerging_topics = []
        for topic in topics:
            frequencies = topic_frequencies[topic]
            doc_counts = topic_doc_counts[topic]

            # Calculate growth rate between periods
            growth_rates = []
            for i in range(1, len(frequencies)):
                prev_freq = max(frequencies[i - 1], 0.01)  # Small epsilon to avoid division by zero
                growth_rate = (frequencies[i] - frequencies[i - 1]) / prev_freq
                growth_rates.append(growth_rate)

            # Topic is emerging if it shows growth and meets minimum presence
            if (
                len(growth_rates) >= 1
                and any(rate > 0.1 for rate in growth_rates)
                and sum(doc_counts) >= 1  # Lower threshold
                and doc_counts[-1] >= doc_counts[0]  # Minimum presence
            ):  # More recent presence
                emerging_topics.append(topic)

        return emerging_topics

    def _calculate_topic_coherence(
        self, topics: List[Topic], document_topics: Dict[int, List[Tuple[Topic, float]]]
    ) -> float:
        """Calculate overall topic coherence."""
        if not topics or not document_topics:
            return 0.0

        coherence_scores = []
        for topic in topics:
            # Calculate pairwise co-occurrence of topic terms
            term_pairs = [
                (t1, t2) for i, t1 in enumerate(topic.keywords) for t2 in topic.keywords[i + 1 :]
            ]

            if not term_pairs:
                continue

            pair_scores = []
            for t1, t2 in term_pairs:
                cooccur_count = sum(
                    1
                    for doc_topics in document_topics.values()
                    if any(
                        t == topic and score >= 0.3 and t1 in t.keywords and t2 in t.keywords
                        for t, score in doc_topics
                    )
                )
                if cooccur_count > 0:
                    # Normalize by topic document count
                    pair_scores.append(cooccur_count / topic.document_count)

            if pair_scores:
                coherence_scores.append(sum(pair_scores) / len(pair_scores))

        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0
