# Content Summarization Guide

## Overview

The content summarization pipeline provides both extractive and abstractive summarization capabilities for feed content. It uses state-of-the-art transformer models (BART and T5) to generate high-quality summaries while maintaining content accuracy and readability.

## Features

- Dual summarization approach (extractive and abstractive)
- Key points extraction
- Configurable summary length
- Quality metrics and confidence scoring
- Performance monitoring
- Error handling and recovery

## Installation

Ensure you have the required dependencies:

```bash
pip install transformers torch numpy prometheus_client
```

The first time you run the summarizer, it will automatically download the required models:
- facebook/bart-large-cnn (for extractive summarization)
- t5-base (for abstractive summarization)

## Basic Usage

```python
from feed_processor.content_analysis import ContentSummarizer

# Initialize the summarizer
summarizer = ContentSummarizer()

# Example content
text = """
Artificial intelligence has made significant strides in recent years, transforming 
various industries and creating new possibilities. Machine learning models can now 
perform complex tasks with remarkable accuracy. Deep learning, in particular, has 
revolutionized fields like computer vision and natural language processing. These 
advances have led to practical applications in healthcare, finance, and autonomous 
vehicles. However, challenges remain in areas such as model interpretability and 
ethical considerations.
"""

# Generate summaries
result = summarizer.summarize(text)

# Access different types of summaries
print("Extractive Summary:", result.extractive_summary)
print("Abstractive Summary:", result.abstractive_summary)
print("Key Points:", result.key_points)

# Access quality metrics
print("Confidence Score:", result.confidence_score)
print("Compression Ratio:", result.compression_ratio)
print("Metadata:", result.metadata)
```

## Advanced Usage

### Controlling Summary Length

```python
# Specify desired summary length
result = summarizer.summarize(text, desired_length=50)
```

### Custom Model Configuration

```python
# Initialize with custom models and parameters
summarizer = ContentSummarizer(
    extractive_model="facebook/bart-large-cnn",
    abstractive_model="t5-base",
    max_length=150,
    min_length=50
)
```

### Batch Processing

```python
def process_articles(articles):
    summaries = []
    for article in articles:
        try:
            summary = summarizer.summarize(article)
            summaries.append(summary)
        except Exception as e:
            print(f"Error processing article: {str(e)}")
    return summaries
```

## Integration with Feed Processing

### Example Pipeline Integration

```python
from feed_processor.content_analysis import ContentSummarizer
from feed_processor.core import FeedProcessor

class EnhancedFeedProcessor(FeedProcessor):
    def __init__(self):
        super().__init__()
        self.summarizer = ContentSummarizer()
    
    def process_item(self, item):
        # Process the feed item
        processed_item = super().process_item(item)
        
        # Add summaries
        if processed_item.content:
            try:
                summary = self.summarizer.summarize(
                    processed_item.content,
                    desired_length=100
                )
                processed_item.summaries = {
                    'extractive': summary.extractive_summary,
                    'abstractive': summary.abstractive_summary,
                    'key_points': summary.key_points
                }
                processed_item.metadata['summary_quality'] = summary.confidence_score
            except Exception as e:
                logger.error(f"Summarization failed: {str(e)}")
        
        return processed_item
```

## Monitoring and Metrics

The summarization pipeline exposes several Prometheus metrics:

### Processing Time

```python
# Histogram of processing time for different operations
content_summarization_processing_seconds_bucket{operation="summarize"}
content_summarization_processing_seconds_bucket{operation="extractive"}
content_summarization_processing_seconds_bucket{operation="abstractive"}
content_summarization_processing_seconds_bucket{operation="key_points"}
```

### Error Tracking

```python
# Counter for different types of errors
content_summarization_errors_total{error_type="extractive_generation"}
content_summarization_errors_total{error_type="abstractive_generation"}
content_summarization_errors_total{error_type="key_points_extraction"}
```

## Quality Metrics

The summarization results include several quality metrics:

1. **Confidence Score** (0-1):
   - Measures agreement between extractive and abstractive summaries
   - Considers coverage of original content
   - Higher scores indicate more reliable summaries

2. **Compression Ratio**:
   - Ratio of summary length to original content length
   - Useful for monitoring summary conciseness

3. **Metadata**:
   - `readability_score`: Measures summary readability
   - `coherence_score`: Measures sentence-to-sentence flow
   - `original_length`: Length of input text
   - `summary_length`: Length of generated summary

## Error Handling

The summarizer includes comprehensive error handling:

```python
try:
    result = summarizer.summarize(text)
except Exception as e:
    if "CUDA out of memory" in str(e):
        # Retry with smaller batch size or on CPU
        summarizer = ContentSummarizer(device="cpu")
        result = summarizer.summarize(text)
    else:
        # Handle other errors
        logger.error(f"Summarization failed: {str(e)}")
```

## Best Practices

1. **Input Preparation**:
   - Clean and normalize text before summarization
   - Remove unnecessary formatting
   - Split very long texts into manageable chunks

2. **Resource Management**:
   - Monitor memory usage with large batches
   - Consider using CPU for very long texts
   - Implement appropriate timeouts

3. **Quality Control**:
   - Monitor confidence scores
   - Validate summaries for critical content
   - Set up alerts for error rates

4. **Performance Optimization**:
   - Use batch processing for multiple articles
   - Cache results when appropriate
   - Monitor and tune model parameters

## Troubleshooting

Common issues and solutions:

1. **Memory Issues**:
   - Reduce batch size
   - Process longer texts in chunks
   - Use CPU instead of GPU

2. **Quality Issues**:
   - Check input text quality
   - Adjust min/max length parameters
   - Validate with confidence scores

3. **Performance Issues**:
   - Monitor processing times
   - Use batch processing
   - Consider model size trade-offs

## Future Enhancements

Planned improvements:

1. **Model Improvements**:
   - Support for more language models
   - Domain-specific fine-tuning
   - Multilingual support

2. **Feature Additions**:
   - Headline generation
   - Multi-document summarization
   - Topic-focused summarization

3. **Integration**:
   - API endpoint for summarization
   - Streaming support
   - Caching layer
