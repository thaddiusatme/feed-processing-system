"""NLP pipeline for content analysis."""

import spacy
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from prometheus_client import Counter, Histogram

# Metrics
nlp_processing_time = Histogram(
    "content_nlp_processing_seconds",
    "Time spent processing content through NLP pipeline",
    ["operation"]
)
nlp_errors = Counter(
    "content_nlp_errors_total",
    "Number of errors in NLP processing",
    ["error_type"]
)

@dataclass
class NLPResult:
    """Container for NLP processing results."""
    tokens: List[str]
    entities: List[Dict[str, Any]]
    noun_phrases: List[str]
    sentences: List[str]
    language: str
    processed_text: str

class NLPPipeline:
    """NLP pipeline for content processing."""
    
    def __init__(self, model: str = "en_core_web_sm"):
        """Initialize NLP pipeline.
        
        Args:
            model: spaCy model to use
        """
        try:
            self.nlp = spacy.load(model)
        except OSError:
            # Download if model not found
            spacy.cli.download(model)
            self.nlp = spacy.load(model)
    
    @nlp_processing_time.labels(operation="process_text").time()
    def process_text(self, text: str) -> NLPResult:
        """Process text through NLP pipeline.
        
        Args:
            text: Text to process
            
        Returns:
            NLPResult containing processed data
        """
        try:
            doc = self.nlp(text)
            
            return NLPResult(
                tokens=[token.text for token in doc],
                entities=[{
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                } for ent in doc.ents],
                noun_phrases=[chunk.text for chunk in doc.noun_chunks],
                sentences=[sent.text for sent in doc.sents],
                language=doc.lang_,
                processed_text=doc.text
            )
        except Exception as e:
            nlp_errors.labels(error_type=type(e).__name__).inc()
            raise
    
    def get_keywords(self, text: str, max_phrases: int = 10) -> List[str]:
        """Extract key phrases from text.
        
        Args:
            text: Text to process
            max_phrases: Maximum number of key phrases to return
            
        Returns:
            List of key phrases
        """
        with nlp_processing_time.labels(operation="get_keywords").time():
            doc = self.nlp(text)
            # Extract noun phrases and named entities
            phrases = set([chunk.text.lower() for chunk in doc.noun_chunks])
            entities = set([ent.text.lower() for ent in doc.ents])
            
            # Combine and sort by length (prefer longer phrases)
            all_phrases = list(phrases.union(entities))
            all_phrases.sort(key=len, reverse=True)
            
            return all_phrases[:max_phrases]
    
    def get_language(self, text: str) -> str:
        """Detect text language.
        
        Args:
            text: Text to analyze
            
        Returns:
            ISO language code
        """
        with nlp_processing_time.labels(operation="get_language").time():
            doc = self.nlp(text)
            return doc.lang_
    
    def get_readability_score(self, text: str) -> float:
        """Calculate text readability score.
        
        Args:
            text: Text to analyze
            
        Returns:
            Readability score (0-100)
        """
        with nlp_processing_time.labels(operation="get_readability").time():
            doc = self.nlp(text)
            
            # Basic implementation of Flesch Reading Ease
            total_sentences = len(list(doc.sents))
            total_words = len([token for token in doc if not token.is_punct])
            total_syllables = sum([len([char for char in token.text if char.lower() in 'aeiou']) 
                                 for token in doc if not token.is_punct])
            
            if total_sentences == 0 or total_words == 0:
                return 0.0
                
            score = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
            return max(0.0, min(100.0, score))  # Clamp between 0 and 100

    def calculate_readability(self, text: str) -> float:
        """Calculate normalized readability score between 0 and 1.
        
        Args:
            text: Text to analyze
            
        Returns:
            Normalized readability score (0-1)
        """
        with nlp_processing_time.labels(operation="calculate_readability").time():
            try:
                raw_score = self.get_readability_score(text)
                # Convert 0-100 scale to 0-1 scale
                return raw_score / 100.0
            except Exception as e:
                nlp_errors.labels(error_type="readability_calculation").inc()
                return 0.5

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords using TF-IDF like scoring.
        
        Args:
            text: Text to analyze
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of keywords
        """
        with nlp_processing_time.labels(operation="extract_keywords").time():
            try:
                doc = self.nlp(text)
                
                # Get word frequencies
                word_freq = {}
                for token in doc:
                    if token.is_alpha and not token.is_stop and len(token.text) > 2:
                        word = token.text.lower()
                        word_freq[word] = word_freq.get(word, 0) + 1
                
                # Score words based on frequency and POS tags
                word_scores = {}
                for token in doc:
                    if token.text.lower() in word_freq:
                        # Base score is frequency
                        score = word_freq[token.text.lower()]
                        
                        # Boost score based on POS tag
                        if token.pos_ in ['PROPN', 'NOUN']:
                            score *= 1.5
                        elif token.pos_ in ['VERB']:
                            score *= 1.2
                        
                        # Boost score if part of named entity
                        if token.ent_type_:
                            score *= 1.3
                            
                        word_scores[token.text.lower()] = score
                
                # Sort by score and return top keywords
                sorted_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
                return [word for word, _ in sorted_words[:max_keywords]]
                
            except Exception as e:
                nlp_errors.labels(error_type="keyword_extraction").inc()
                return []

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze text sentiment using spaCy's pattern matcher.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment scores
        """
        with nlp_processing_time.labels(operation="analyze_sentiment").time():
            try:
                doc = self.nlp(text)
                
                # Initialize sentiment counters
                positive_words = 0
                negative_words = 0
                total_words = 0
                
                # Simple sentiment analysis using spaCy's token attributes
                for token in doc:
                    if token.is_alpha and not token.is_stop:
                        total_words += 1
                        # Use lexical attributes for basic sentiment
                        if token.pos_ in ['ADJ', 'VERB', 'ADV']:
                            # This is a simplified approach - in production you'd want
                            # to use a proper sentiment lexicon
                            if token._.polarity > 0:
                                positive_words += 1
                            elif token._.polarity < 0:
                                negative_words += 1
                
                if total_words == 0:
                    return {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
                
                # Calculate sentiment ratios
                positive_ratio = positive_words / total_words
                negative_ratio = negative_words / total_words
                neutral_ratio = 1.0 - (positive_ratio + negative_ratio)
                
                return {
                    'positive': positive_ratio,
                    'negative': negative_ratio,
                    'neutral': neutral_ratio
                }
                
            except Exception as e:
                nlp_errors.labels(error_type="sentiment_analysis").inc()
                return {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
