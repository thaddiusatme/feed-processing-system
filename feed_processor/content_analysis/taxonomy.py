"""Category taxonomy for content classification."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class ContentCategory(Enum):
    """Main content categories."""

    TECHNOLOGY = "technology"
    BUSINESS = "business"
    SCIENCE = "science"
    HEALTH = "health"
    POLITICS = "politics"
    ENTERTAINMENT = "entertainment"
    SPORTS = "sports"
    EDUCATION = "education"
    LIFESTYLE = "lifestyle"
    TRAVEL = "travel"


@dataclass
class CategoryNode:
    """Node in the category taxonomy tree."""

    name: str
    parent: Optional["CategoryNode"] = None
    children: List["CategoryNode"] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)
    description: str = ""


class CategoryTaxonomy:
    """Hierarchical category taxonomy."""

    def __init__(self):
        """Initialize category taxonomy."""
        self.root = CategoryNode("root")
        self.categories: Dict[str, CategoryNode] = {}
        self._initialize_taxonomy()

    def _initialize_taxonomy(self):
        """Initialize the category hierarchy and keywords."""
        # Technology categories
        tech = self._add_category(
            "technology",
            keywords={
                "software",
                "hardware",
                "programming",
                "artificial intelligence",
                "machine learning",
                "cybersecurity",
                "blockchain",
                "cloud computing",
            },
        )
        self._add_category(
            "ai",
            parent=tech,
            keywords={
                "machine learning",
                "deep learning",
                "neural networks",
                "artificial intelligence",
                "nlp",
                "computer vision",
            },
        )
        self._add_category(
            "cybersecurity",
            parent=tech,
            keywords={
                "security",
                "hacking",
                "encryption",
                "privacy",
                "cyber attack",
                "malware",
                "ransomware",
                "data breach",
            },
        )

        # Business categories
        business = self._add_category(
            "business",
            keywords={
                "finance",
                "economy",
                "market",
                "startup",
                "investment",
                "entrepreneurship",
                "management",
                "strategy",
            },
        )
        self._add_category(
            "finance",
            parent=business,
            keywords={
                "investing",
                "stock market",
                "cryptocurrency",
                "banking",
                "financial markets",
                "trading",
                "investment",
            },
        )
        self._add_category(
            "startups",
            parent=business,
            keywords={
                "startup",
                "venture capital",
                "entrepreneurship",
                "funding",
                "seed round",
                "series a",
                "angel investor",
            },
        )

        # Science categories
        science = self._add_category(
            "science",
            keywords={
                "research",
                "discovery",
                "experiment",
                "scientific",
                "innovation",
                "laboratory",
                "study",
            },
        )
        self._add_category(
            "physics",
            parent=science,
            keywords={
                "quantum",
                "particle physics",
                "theoretical physics",
                "astrophysics",
                "physics research",
            },
        )
        self._add_category(
            "biology",
            parent=science,
            keywords={
                "genetics",
                "molecular biology",
                "evolution",
                "cell biology",
                "biotechnology",
                "microbiology",
            },
        )

        # Add more categories as needed...

    def _add_category(
        self, name: str, parent: Optional[CategoryNode] = None, keywords: Optional[Set[str]] = None
    ) -> CategoryNode:
        """Add a category to the taxonomy.

        Args:
            name: Category name
            parent: Parent category node
            keywords: Category keywords

        Returns:
            Created category node
        """
        if parent is None:
            parent = self.root

        node = CategoryNode(name=name, parent=parent, keywords=keywords or set())
        parent.children.append(node)
        self.categories[name] = node
        return node

    def get_category(self, name: str) -> Optional[CategoryNode]:
        """Get category node by name.

        Args:
            name: Category name

        Returns:
            Category node if found, None otherwise
        """
        return self.categories.get(name.lower())

    def get_parent_categories(self, category: str) -> List[str]:
        """Get list of parent categories.

        Args:
            category: Category name

        Returns:
            List of parent category names
        """
        node = self.get_category(category)
        if not node:
            return []

        parents = []
        current = node.parent
        while current and current != self.root:
            parents.append(current.name)
            current = current.parent
        return parents

    def get_subcategories(self, category: str) -> List[str]:
        """Get list of subcategories.

        Args:
            category: Category name

        Returns:
            List of subcategory names
        """
        node = self.get_category(category)
        if not node:
            return []
        return [child.name for child in node.children]

    def get_category_keywords(self, category: str) -> Set[str]:
        """Get keywords for a category.

        Args:
            category: Category name

        Returns:
            Set of keywords
        """
        node = self.get_category(category)
        if not node:
            return set()

        # Include keywords from parent categories
        keywords = set()
        current = node
        while current and current != self.root:
            keywords.update(current.keywords)
            current = current.parent
        return keywords
