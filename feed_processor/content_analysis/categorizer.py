"""Content categorization using NLP and taxonomy."""

from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import Counter
from prometheus_client import Counter, Histogram

from .nlp_pipeline import NLPPipeline
from .taxonomy import CategoryTaxonomy, ContentCategory

# Metrics
categorization_time = Histogram(
    "content_categorization_seconds",
    "Time spent categorizing content",
    ["operation"]
)
categorization_errors = Counter(
    "content_categorization_errors_total",
    "Number of errors in content categorization",
    ["error_type"]
)

@dataclass
class CategorizationResult:
    """Result of content categorization."""
    primary_category: ContentCategory
    secondary_categories: List[ContentCategory]
    confidence_scores: Dict[ContentCategory, float]
    keywords: List[str]
    language: str
    readability_score: float

class ContentCategorizer:
    """Content categorizer using NLP and taxonomy."""
    
    def __init__(self, nlp_model: str = "en_core_web_sm"):
        """Initialize content categorizer.
        
        Args:
            nlp_model: spaCy model to use
        """
        self.nlp = NLPPipeline(nlp_model)
        self.taxonomy = CategoryTaxonomy()
        
    @categorization_time.labels(operation="categorize").time()
    def categorize(self, text: str, title: str = "") -> CategorizationResult:
        """Categorize content using NLP and taxonomy.
        
        Args:
            text: Main content text
            title: Optional content title
            
        Returns:
            CategorizationResult with categories and confidence scores
        """
        try:
            # Process text through NLP pipeline
            nlp_result = self.nlp.process_text(text)
            
            # Extract keywords
            keywords = self.nlp.get_keywords(text)
            if title:
                title_keywords = self.nlp.get_keywords(title)
                # Prioritize title keywords
                keywords = list(dict.fromkeys(title_keywords + keywords))
            
            # Calculate category scores
            category_scores = self._calculate_category_scores(
                keywords=keywords,
                entities=nlp_result.entities,
                noun_phrases=nlp_result.noun_phrases
            )
            
            # Get top categories
            sorted_categories = sorted(
                category_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            primary_category = ContentCategory(sorted_categories[0][0])
            secondary_categories = [
                ContentCategory(cat) for cat, _ in sorted_categories[1:3]
            ]
            
            # Calculate readability score
            readability_score = self.nlp.get_readability_score(text)
            
            return CategorizationResult(
                primary_category=primary_category,
                secondary_categories=secondary_categories,
                confidence_scores={
                    ContentCategory(cat): score 
                    for cat, score in category_scores.items()
                },
                keywords=keywords[:10],  # Top 10 keywords
                language=nlp_result.language,
                readability_score=readability_score
            )
            
        except Exception as e:
            categorization_errors.labels(error_type=type(e).__name__).inc()
            raise
            
    def _calculate_category_scores(
        self,
        keywords: List[str],
        entities: List[Dict[str, str]],
        noun_phrases: List[str]
    ) -> Dict[str, float]:
        """Calculate confidence scores for each category.
        
        Args:
            keywords: Extracted keywords
            entities: Named entities
            noun_phrases: Noun phrases
            
        Returns:
            Dictionary of category scores
        """
        # Initialize scores
        scores: Dict[str, float] = {
            cat.value: 0.0 for cat in ContentCategory
        }
        
        # Weight factors
        KEYWORD_WEIGHT = 1.0
        ENTITY_WEIGHT = 0.8
        NOUN_PHRASE_WEIGHT = 0.6
        
        # Process keywords
        for keyword in keywords:
            for category in ContentCategory:
                if keyword.lower() in self.taxonomy.get_category_keywords(category.value):
                    scores[category.value] += KEYWORD_WEIGHT
                    
        # Process entities
        for entity in entities:
            entity_text = entity["text"].lower()
            for category in ContentCategory:
                if entity_text in self.taxonomy.get_category_keywords(category.value):
                    scores[category.value] += ENTITY_WEIGHT
                    
        # Process noun phrases
        for phrase in noun_phrases:
            phrase_lower = phrase.lower()
            for category in ContentCategory:
                if phrase_lower in self.taxonomy.get_category_keywords(category.value):
                    scores[category.value] += NOUN_PHRASE_WEIGHT
                    
        # Normalize scores
        max_score = max(scores.values()) if scores.values() else 1.0
        if max_score > 0:
            scores = {
                cat: score / max_score 
                for cat, score in scores.items()
            }
            
        return scores
        
    def get_category_keywords(self, category: ContentCategory) -> List[str]:
        """Get keywords associated with a category.
        
        Args:
            category: Content category
            
        Returns:
            List of category keywords
        """
        return list(self.taxonomy.get_category_keywords(category.value))
