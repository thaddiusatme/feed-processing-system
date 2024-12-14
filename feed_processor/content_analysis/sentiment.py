"""Sentiment analysis for content processing."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from transformers import pipeline
import numpy as np
from prometheus_client import Counter, Histogram

# Metrics
sentiment_processing_time = Histogram(
    "content_sentiment_processing_seconds",
    "Time spent processing sentiment analysis",
    ["operation"]
)
sentiment_errors = Counter(
    "content_sentiment_errors_total",
    "Number of errors in sentiment analysis",
    ["error_type"]
)

@dataclass
class EntitySentiment:
    """Sentiment information for a specific entity."""
    entity: str
    sentiment_score: float  # -1 to 1
    confidence: float
    mentions: List[Dict[str, int]]  # List of {start, end} positions

@dataclass
class SentimentResult:
    """Complete sentiment analysis result."""
    overall_sentiment: float  # -1 to 1
    overall_confidence: float
    entity_sentiments: List[EntitySentiment]
    aspect_sentiments: Dict[str, float]
    sentence_sentiments: List[Tuple[str, float]]

class SentimentAnalyzer:
    """Sentiment analysis using transformer models."""
    
    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
        """Initialize sentiment analyzer.
        
        Args:
            model_name: Name of the pretrained model to use
        """
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=model_name,
            truncation=True
        )
        # Aspect-based sentiment model
        self.aspect_pipeline = pipeline(
            "text-classification",
            model="nlptown/bert-base-multilingual-uncased-sentiment",
            truncation=True
        )
    
    @sentiment_processing_time.labels(operation="analyze").time()
    def analyze(self, text: str, entities: Optional[List[Dict]] = None) -> SentimentResult:
        """Perform comprehensive sentiment analysis.
        
        Args:
            text: Text to analyze
            entities: Optional list of entities with positions
            
        Returns:
            SentimentResult containing overall and entity-level sentiment
        """
        try:
            # Overall sentiment
            overall_result = self.sentiment_pipeline(text)[0]
            overall_sentiment = self._normalize_sentiment_score(
                overall_result["score"],
                overall_result["label"]
            )
            
            # Sentence-level sentiment
            sentences = text.split(". ")
            sentence_sentiments = []
            for sentence in sentences:
                if not sentence.strip():
                    continue
                result = self.sentiment_pipeline(sentence)[0]
                sentiment = self._normalize_sentiment_score(
                    result["score"],
                    result["label"]
                )
                sentence_sentiments.append((sentence, sentiment))
            
            # Entity-level sentiment
            entity_sentiments = []
            if entities:
                entity_sentiments = self._analyze_entity_sentiments(text, entities)
            
            # Aspect-based sentiment
            aspect_sentiments = self._analyze_aspect_sentiments(text)
            
            return SentimentResult(
                overall_sentiment=overall_sentiment,
                overall_confidence=overall_result["score"],
                entity_sentiments=entity_sentiments,
                aspect_sentiments=aspect_sentiments,
                sentence_sentiments=sentence_sentiments
            )
            
        except Exception as e:
            sentiment_errors.labels(error_type=type(e).__name__).inc()
            raise
    
    def _normalize_sentiment_score(self, score: float, label: str) -> float:
        """Normalize sentiment score to range [-1, 1].
        
        Args:
            score: Raw sentiment score
            label: Sentiment label
            
        Returns:
            Normalized sentiment score
        """
        if label.lower() in ["negative", "1 star", "2 stars"]:
            return -score
        return score
    
    @sentiment_processing_time.labels(operation="entity_sentiment").time()
    def _analyze_entity_sentiments(
        self,
        text: str,
        entities: List[Dict]
    ) -> List[EntitySentiment]:
        """Analyze sentiment for specific entities.
        
        Args:
            text: Full text
            entities: List of entities with positions
            
        Returns:
            List of EntitySentiment objects
        """
        entity_sentiments = []
        
        for entity_info in entities:
            entity_text = entity_info["text"]
            # Find all mentions of this entity
            mentions = self._find_entity_mentions(text, entity_text)
            
            # Analyze sentiment in context windows around mentions
            sentiments = []
            confidences = []
            
            for start, end in mentions:
                # Get context window (50 chars before and after)
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                context = text[context_start:context_end]
                
                result = self.sentiment_pipeline(context)[0]
                sentiment = self._normalize_sentiment_score(
                    result["score"],
                    result["label"]
                )
                sentiments.append(sentiment)
                confidences.append(result["score"])
            
            if sentiments:
                # Average sentiment and confidence
                avg_sentiment = np.mean(sentiments)
                avg_confidence = np.mean(confidences)
                
                entity_sentiments.append(EntitySentiment(
                    entity=entity_text,
                    sentiment_score=float(avg_sentiment),
                    confidence=float(avg_confidence),
                    mentions=[{"start": s, "end": e} for s, e in mentions]
                ))
        
        return entity_sentiments
    
    def _find_entity_mentions(self, text: str, entity: str) -> List[Tuple[int, int]]:
        """Find all mentions of an entity in text.
        
        Args:
            text: Text to search
            entity: Entity to find
            
        Returns:
            List of (start, end) positions
        """
        mentions = []
        start = 0
        while True:
            start = text.lower().find(entity.lower(), start)
            if start == -1:
                break
            mentions.append((start, start + len(entity)))
            start += len(entity)
        return mentions
    
    @sentiment_processing_time.labels(operation="aspect_sentiment").time()
    def _analyze_aspect_sentiments(self, text: str) -> Dict[str, float]:
        """Analyze sentiment for different aspects of the content.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of aspect sentiments
        """
        # Define common aspects to analyze
        aspects = {
            "quality": ["quality", "standard", "excellence"],
            "reliability": ["reliable", "consistent", "dependable"],
            "performance": ["performance", "speed", "efficiency"],
            "usability": ["usable", "user-friendly", "accessible"],
            "value": ["value", "worth", "cost-effective"]
        }
        
        aspect_sentiments = {}
        
        for aspect, keywords in aspects.items():
            # Find sentences containing aspect keywords
            relevant_sentences = []
            for sentence in text.split(". "):
                if any(keyword in sentence.lower() for keyword in keywords):
                    relevant_sentences.append(sentence)
            
            if relevant_sentences:
                # Analyze sentiment for relevant sentences
                sentiments = []
                for sentence in relevant_sentences:
                    result = self.aspect_pipeline(sentence)[0]
                    # Convert 1-5 scale to -1 to 1
                    sentiment = (int(result["label"][0]) - 3) / 2
                    sentiments.append(sentiment)
                
                aspect_sentiments[aspect] = float(np.mean(sentiments))
        
        return aspect_sentiments
