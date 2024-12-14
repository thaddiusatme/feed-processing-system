# Content Summarization Examples and Use Cases

## Real-World Examples

### 1. News Article Summarization

```python
from feed_processor.content_analysis import ContentSummarizer

# Initialize summarizer
summarizer = ContentSummarizer()

# Example news article
news_article = """
In a groundbreaking development, researchers at MIT have created a new type of
artificial neural network that can learn from significantly less data than
traditional models. The innovation, published today in Nature, combines
principles from neuroscience with machine learning algorithms. The team
demonstrated that their system can achieve similar accuracy to conventional
neural networks while using only 10% of the training data. This breakthrough
could make AI more accessible to applications where large datasets are not
available, such as rare disease diagnosis or small business analytics. The
researchers also noted improved interpretability of the model's decisions,
addressing a common criticism of deep learning systems. Industry experts have
called this development a significant step forward in making AI more practical
and accessible for real-world applications.
"""

# Generate summary with different lengths
short_summary = summarizer.summarize(news_article, desired_length=30)
medium_summary = summarizer.summarize(news_article, desired_length=50)
detailed_summary = summarizer.summarize(news_article, desired_length=100)

print("Short Summary:", short_summary.abstractive_summary)
print("Key Points:", short_summary.key_points)
print("Confidence:", short_summary.confidence_score)
```

### 2. Technical Documentation Summary

```python
# Example of summarizing technical documentation
tech_doc = """
The PostgreSQL VACUUM command is an essential maintenance operation that reclaims
storage occupied by dead tuples. When you delete or update a row in PostgreSQL,
the database doesn't immediately remove the old version of the row. Instead, it
marks it as invalid and creates a new version. These invalid rows, called dead
tuples, accumulate over time and can impact performance. VACUUM identifies and
marks these dead tuples as space that can be reused by future operations.
Additionally, VACUUM updates the visibility map, which helps optimize index-only
scans. The ANALYZE option, often used with VACUUM, updates statistics about the
contents of tables, which the query planner uses to determine optimal execution
plans.
"""

# Configure summarizer for technical content
tech_summarizer = ContentSummarizer(
    extractive_model="facebook/bart-large-cnn",
    max_length=80,
    min_length=40
)

result = tech_summarizer.summarize(tech_doc)
print("Technical Summary:", result.extractive_summary)
print("Key Technical Points:", result.key_points)
```

### 3. Multi-Document Summarization

```python
from feed_processor.content_analysis import ContentSummarizer

# Initialize summarizer
summarizer = ContentSummarizer()

# Example related articles about a technology announcement
article1 = """
Apple today announced its latest M3 chip series, marking a significant leap in
Mac performance. The new chips, built on 3-nanometer technology, offer up to
60% faster CPU performance than M1. The company claims these processors will
revolutionize professional workflows and gaming on Mac platforms.
"""

article2 = """
Industry analysts predict Apple's new M3 chips will significantly impact the
PC market. Benchmark tests show the M3 outperforming competing processors in
both performance and energy efficiency. The 3nm manufacturing process gives
Apple a temporary advantage in the market, as competitors are still using 5nm
technology.
"""

article3 = """
Software developers are rapidly updating their applications to take advantage
of Apple's M3 architecture. Professional tools like Adobe Creative Suite and
DaVinci Resolve have announced optimized versions coming in December 2023.
Gaming companies are also showing increased interest in Mac development due
to the M3's enhanced graphics capabilities.
"""

# Generate multi-document summary with timeline
result = summarizer.summarize_multiple(
    documents=[article1, article2, article3],
    desired_length=150,
    identify_timeline=True
)

print("Combined Summary:", result.extractive_summary)
print("\nCommon Themes:", result.common_themes)
print("\nKey Points:", result.key_points)
print("\nTimeline:", result.timeline)
print("\nCross-references:", result.cross_references)
print("\nConfidence Score:", result.confidence_score)
```

Example output:
```
Combined Summary: Apple's new M3 chip series represents a major advancement in Mac
performance, built on 3-nanometer technology offering 60% faster CPU performance
than M1. Benchmark tests demonstrate superior performance and energy efficiency
compared to competitors. Software developers, including Adobe and DaVinci Resolve,
are optimizing their applications for the M3 architecture, with gaming companies
showing increased interest due to enhanced graphics capabilities.

Common Themes: ['m3 chip', 'performance improvement', 'software optimization',
'nanometer technology', 'gaming capabilities']

Key Points:
- M3 chips built on 3nm technology
- 60% faster CPU performance than M1
- Software optimization by major developers
- Enhanced gaming capabilities
- Market advantage over competitors

Timeline:
[
    {
        "date": "2023-12-01T00:00:00",
        "content": "Professional tools like Adobe Creative Suite and DaVinci
        Resolve have announced optimized versions coming in December 2023"
    }
]

Cross-references:
[
    {
        "doc1_index": 0,
        "doc2_index": 1,
        "relationship": "related",
        "similarity_score": 0.72
    },
    {
        "doc1_index": 0,
        "doc2_index": 2,
        "relationship": "related",
        "similarity_score": 0.65
    }
]

Confidence Score: 0.85
```

### 4. Research Paper Analysis

```python
# Example of analyzing multiple research paper sections
class ResearchSummarizer:
    def __init__(self):
        self.summarizer = ContentSummarizer()

    def generate_abstract(self, paper_sections):
        """Generate a comprehensive abstract from paper sections."""
        result = self.summarizer.summarize_multiple(
            documents=paper_sections,
            desired_length=250,
            identify_timeline=False
        )

        return {
            'abstract': result.abstractive_summary,
            'key_findings': result.key_points,
            'themes': result.common_themes,
            'section_relationships': result.cross_references
        }

# Example usage
paper_sections = {
    'introduction': """[Introduction text]""",
    'methodology': """[Methodology text]""",
    'results': """[Results text]""",
    'discussion': """[Discussion text]"""
}

research_summarizer = ResearchSummarizer()
abstract = research_summarizer.generate_abstract(list(paper_sections.values()))
```

The multi-document summarization feature is particularly useful for:
- Analyzing related news articles
- Summarizing research papers
- Processing multiple document versions
- Creating executive summaries from reports
- Tracking topic evolution across time

Key benefits:
1. Identifies common themes across documents
2. Maintains context and relationships between documents
3. Extracts chronological information when available
4. Provides confidence scores for summary quality
5. Generates both extractive and abstractive summaries

### 5. Social Media Content Analysis

```python
class SocialMediaAnalyzer:
    def __init__(self):
        self.summarizer = ContentSummarizer()

    def analyze_thread(self, posts):
        # Combine posts into a coherent narrative
        thread_text = " ".join(posts)

        # Generate brief summary
        summary = self.summarizer.summarize(
            thread_text,
            desired_length=30  # Keep it tweet-length
        )

        return {
            'summary': summary.abstractive_summary,
            'key_points': summary.key_points[:3],  # Top 3 points
            'engagement_potential': summary.metadata['readability_score']
        }

# Example usage
social_posts = [
    "Initial post about a trending topic...",
    "Follow-up with additional details...",
    "Community responses and discussion..."
]

analyzer = SocialMediaAnalyzer()
analysis = analyzer.analyze_thread(social_posts)
print("Thread Summary:", analysis['summary'])
print("Key Points:", analysis['key_points'])
```

### 6. Content Curation System

```python
class ContentCurator:
    def __init__(self):
        self.summarizer = ContentSummarizer()

    def curate_content(self, articles, target_length=500):
        summaries = []

        for article in articles:
            # Generate summary and metadata
            summary = self.summarizer.summarize(article['content'])

            summaries.append({
                'title': article['title'],
                'summary': summary.abstractive_summary,
                'key_points': summary.key_points,
                'quality_score': summary.confidence_score,
                'reading_time': len(summary.abstractive_summary.split()) // 200  # words per minute
            })

        # Sort by quality score
        summaries.sort(key=lambda x: x['quality_score'], reverse=True)

        return summaries

# Example usage
articles = [
    {'title': 'Article 1', 'content': 'Content 1...'},
    {'title': 'Article 2', 'content': 'Content 2...'},
    # ... more articles
]

curator = ContentCurator()
curated_content = curator.curate_content(articles)
for content in curated_content:
    print(f"Title: {content['title']}")
    print(f"Summary: {content['summary']}")
    print(f"Quality Score: {content['quality_score']}")
```

## Performance Tips

1. **Batch Processing for Multiple Documents**:
```python
def batch_process(documents, batch_size=5):
    summaries = []
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            batch_summaries = list(executor.map(
                summarizer.summarize,
                batch
            ))
        summaries.extend(batch_summaries)
    return summaries
```

2. **Memory-Efficient Processing**:
```python
def process_large_document(text, chunk_size=1000):
    # Split into chunks by words
    words = text.split()
    chunks = [
        ' '.join(words[i:i + chunk_size])
        for i in range(0, len(words), chunk_size)
    ]

    # Summarize each chunk
    chunk_summaries = [
        summarizer.summarize(chunk).abstractive_summary
        for chunk in chunks
    ]

    # Create final summary
    return summarizer.summarize(' '.join(chunk_summaries))
```

3. **Quality-Focused Processing**:
```python
def quality_focused_summary(text, min_confidence=0.7):
    summary = summarizer.summarize(text)

    # If confidence is low, try different approaches
    if summary.confidence_score < min_confidence:
        # Try extractive only
        extractive_summary = summarizer._generate_extractive_summary(
            text,
            max_length=100,
            min_length=50
        )
        return extractive_summary

    return summary.abstractive_summary
```
