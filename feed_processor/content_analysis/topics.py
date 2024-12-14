"""Topic extraction and clustering for content analysis."""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from collections import defaultdict
from prometheus_client import Counter, Histogram

from .nlp_pipeline import NLPPipeline

# Metrics
topic_processing_time = Histogram(
    "content_topic_processing_seconds",
    "Time spent processing topic analysis",
    ["operation"]
)
topic_errors = Counter(
    "content_topic_errors_total",
    "Number of errors in topic analysis",
    ["error_type"]
)

@dataclass
class Topic:
    """Represents a topic cluster."""
    id: int
    keywords: List[str]
    representative_texts: List[str]
    size: int
    coherence_score: float
    creation_date: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

@dataclass
class TopicTrend:
    """Represents trend information for a topic."""
    topic_id: int
    volume_trend: List[Tuple[datetime, int]]  # (timestamp, count)
    sentiment_trend: List[Tuple[datetime, float]]  # (timestamp, sentiment)
    engagement_trend: List[Tuple[datetime, float]]  # (timestamp, engagement)
    related_topics: List[Tuple[int, float]]  # (topic_id, correlation)

@dataclass
class TopicAnalysisResult:
    """Result of topic analysis."""
    topics: List[Topic]
    document_topics: Dict[str, List[Tuple[int, float]]]  # doc_id -> [(topic_id, score)]
    topic_trends: Dict[int, TopicTrend]
    emerging_topics: List[int]  # topic_ids
    trending_topics: List[int]  # topic_ids

class TopicAnalyzer:
    """Topic analysis using clustering and trend detection."""
    
    def __init__(self, nlp_model: str = "en_core_web_sm"):
        """Initialize topic analyzer.
        
        Args:
            nlp_model: spaCy model to use
        """
        self.nlp = NLPPipeline(nlp_model)
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.topic_history: Dict[int, Topic] = {}
        self.trend_data: Dict[int, TopicTrend] = {}
    
    @topic_processing_time.labels(operation="extract_topics").time()
    def extract_topics(
        self,
        documents: List[Dict[str, str]],  # List of {id: str, text: str}
        min_cluster_size: int = 3,
        max_distance: float = 0.7
    ) -> TopicAnalysisResult:
        """Extract topics from documents using clustering.
        
        Args:
            documents: List of documents to analyze
            min_cluster_size: Minimum number of documents per cluster
            max_distance: Maximum distance between points in cluster
            
        Returns:
            TopicAnalysisResult containing topics and trends
        """
        try:
            # Prepare documents
            doc_texts = [doc["text"] for doc in documents]
            doc_ids = [doc["id"] for doc in documents]
            
            # Vectorize documents
            vectors = self.vectorizer.fit_transform(doc_texts)
            
            # Cluster documents
            clusters = DBSCAN(
                eps=max_distance,
                min_samples=min_cluster_size,
                metric='cosine'
            ).fit(vectors)
            
            # Extract topics from clusters
            topics = []
            doc_topics: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
            
            for cluster_id in set(clusters.labels_):
                if cluster_id == -1:  # Noise points
                    continue
                    
                # Get documents in cluster
                cluster_docs = [
                    doc_texts[i] for i, label in enumerate(clusters.labels_)
                    if label == cluster_id
                ]
                cluster_ids = [
                    doc_ids[i] for i, label in enumerate(clusters.labels_)
                    if label == cluster_id
                ]
                
                # Extract keywords for topic
                keywords = self._extract_cluster_keywords(cluster_docs)
                
                # Calculate topic coherence
                coherence = self._calculate_coherence(cluster_docs)
                
                # Create topic
                topic = Topic(
                    id=cluster_id,
                    keywords=keywords,
                    representative_texts=self._get_representative_texts(cluster_docs),
                    size=len(cluster_docs),
                    coherence_score=coherence
                )
                topics.append(topic)
                
                # Update topic history
                self._update_topic_history(topic)
                
                # Assign documents to topic
                for doc_id in cluster_ids:
                    doc_topics[doc_id].append((cluster_id, 1.0))
            
            # Update trend data
            self._update_trend_data(topics, documents)
            
            # Identify emerging and trending topics
            emerging = self._identify_emerging_topics()
            trending = self._identify_trending_topics()
            
            return TopicAnalysisResult(
                topics=topics,
                document_topics=dict(doc_topics),
                topic_trends=self.trend_data,
                emerging_topics=emerging,
                trending_topics=trending
            )
            
        except Exception as e:
            topic_errors.labels(error_type=type(e).__name__).inc()
            raise
    
    def _extract_cluster_keywords(self, texts: List[str], top_n: int = 10) -> List[str]:
        """Extract representative keywords for a cluster.
        
        Args:
            texts: List of texts in cluster
            top_n: Number of keywords to extract
            
        Returns:
            List of keywords
        """
        # Use TF-IDF to find distinctive terms
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            ngram_range=(1, 2)
        )
        tfidf = vectorizer.fit_transform(texts)
        
        # Get average TF-IDF scores
        avg_scores = np.array(tfidf.mean(axis=0))[0]
        
        # Get top terms
        top_indices = avg_scores.argsort()[-top_n:][::-1]
        feature_names = vectorizer.get_feature_names_out()
        
        return [feature_names[i] for i in top_indices]
    
    def _calculate_coherence(self, texts: List[str]) -> float:
        """Calculate topic coherence score.
        
        Args:
            texts: List of texts in topic
            
        Returns:
            Coherence score (0-1)
        """
        # Simple coherence based on document similarity
        vectors = self.vectorizer.transform(texts)
        similarities = (vectors * vectors.T).A
        return float(np.mean(similarities))
    
    def _get_representative_texts(
        self,
        texts: List[str],
        max_texts: int = 3
    ) -> List[str]:
        """Get most representative texts for a topic.
        
        Args:
            texts: List of texts in topic
            max_texts: Maximum number of texts to return
            
        Returns:
            List of representative texts
        """
        if len(texts) <= max_texts:
            return texts
            
        # Use center points as representatives
        vectors = self.vectorizer.transform(texts)
        centroid = vectors.mean(axis=0)
        
        # Calculate distances to centroid
        distances = np.squeeze(np.asarray(vectors.dot(centroid.T)))
        top_indices = distances.argsort()[-max_texts:][::-1]
        
        return [texts[i] for i in top_indices]
    
    def _update_topic_history(self, topic: Topic):
        """Update topic history with new topic information.
        
        Args:
            topic: New topic information
        """
        if topic.id in self.topic_history:
            existing = self.topic_history[topic.id]
            # Update existing topic
            existing.size = topic.size
            existing.keywords = topic.keywords
            existing.coherence_score = topic.coherence_score
            existing.last_updated = datetime.utcnow()
        else:
            # Add new topic
            self.topic_history[topic.id] = topic
    
    def _update_trend_data(
        self,
        current_topics: List[Topic],
        documents: List[Dict[str, str]]
    ):
        """Update trend data with new topic information.
        
        Args:
            current_topics: Current topics
            documents: Current documents
        """
        current_time = datetime.utcnow()
        
        for topic in current_topics:
            if topic.id not in self.trend_data:
                self.trend_data[topic.id] = TopicTrend(
                    topic_id=topic.id,
                    volume_trend=[],
                    sentiment_trend=[],
                    engagement_trend=[],
                    related_topics=[]
                )
            
            trend = self.trend_data[topic.id]
            
            # Update volume trend
            trend.volume_trend.append((current_time, topic.size))
            
            # Keep only last 30 days of data
            cutoff = current_time - datetime.timedelta(days=30)
            trend.volume_trend = [
                (t, v) for t, v in trend.volume_trend
                if t >= cutoff
            ]
            
            # Update related topics
            related = self._find_related_topics(topic.id, current_topics)
            trend.related_topics = related
    
    def _find_related_topics(
        self,
        topic_id: int,
        topics: List[Topic]
    ) -> List[Tuple[int, float]]:
        """Find topics related to given topic.
        
        Args:
            topic_id: Topic to find relations for
            topics: Current topics
            
        Returns:
            List of (topic_id, correlation) pairs
        """
        target = next(t for t in topics if t.id == topic_id)
        relations = []
        
        for other in topics:
            if other.id == topic_id:
                continue
                
            # Calculate keyword overlap
            overlap = len(
                set(target.keywords).intersection(other.keywords)
            ) / len(set(target.keywords).union(other.keywords))
            
            if overlap > 0.1:  # Minimum overlap threshold
                relations.append((other.id, overlap))
        
        return sorted(relations, key=lambda x: x[1], reverse=True)[:5]
    
    def _identify_emerging_topics(self) -> List[int]:
        """Identify emerging topics based on growth rate.
        
        Returns:
            List of emerging topic IDs
        """
        emerging = []
        for topic_id, trend in self.trend_data.items():
            if len(trend.volume_trend) < 2:
                continue
                
            # Calculate growth rate
            recent = trend.volume_trend[-1][1]  # Current volume
            previous = trend.volume_trend[-2][1]  # Previous volume
            
            if previous > 0 and (recent / previous) > 1.5:  # 50% growth
                emerging.append(topic_id)
        
        return emerging
    
    def _identify_trending_topics(self) -> List[int]:
        """Identify trending topics based on sustained growth.
        
        Returns:
            List of trending topic IDs
        """
        trending = []
        for topic_id, trend in self.trend_data.items():
            if len(trend.volume_trend) < 7:  # Need at least a week of data
                continue
                
            # Calculate weekly growth
            volumes = [v for _, v in trend.volume_trend[-7:]]
            if len(volumes) < 7:
                continue
                
            # Check for sustained growth
            is_trending = all(
                volumes[i] <= volumes[i + 1]
                for i in range(len(volumes) - 1)
            )
            
            if is_trending:
                trending.append(topic_id)
        
        return trending
