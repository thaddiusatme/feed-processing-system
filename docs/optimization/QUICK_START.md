# Feed Processor Optimization Quick Start Guide

This guide will help you quickly set up and use the Feed Processor's optimization features.

## 1. Enable Optimization

The optimization system is enabled by default. To use it with default settings, no additional configuration is needed:

```python
from feed_processor.core.processor import FeedProcessor

processor = FeedProcessor(
    inoreader_token="your_token",
    webhook_url="your_webhook_url"
)
```

## 2. Custom Configuration

If you need to customize the optimization behavior:

```python
from feed_processor.config.processor_config import ProcessorConfig

config = ProcessorConfig(
    # Adjust these based on your needs
    batch_size=100,          # Starting batch size
    target_cpu_usage=70.0,   # Target CPU utilization
    concurrent_processors=4   # Starting thread count
)

processor = FeedProcessor(
    inoreader_token="your_token",
    webhook_url="your_webhook_url",
    config=config
)
```

## 3. Monitor Performance

1. Open the Grafana dashboard at `http://your-server:3000`
2. Load the "Feed Processor Optimization" dashboard
3. Monitor these key metrics:
   - Processing batch size
   - Thread count
   - Processing rate
   - Average processing time

## 4. Common Configurations

### High-Performance Setup
```python
config = ProcessorConfig(
    batch_size=200,
    max_batch_size=1000,
    concurrent_processors=8,
    target_cpu_usage=80.0
)
```

### Conservative Setup
```python
config = ProcessorConfig(
    batch_size=50,
    max_batch_size=200,
    concurrent_processors=2,
    target_cpu_usage=50.0
)
```

### Balanced Setup (Default)
```python
config = ProcessorConfig(
    batch_size=100,
    max_batch_size=500,
    concurrent_processors=4,
    target_cpu_usage=70.0
)
```

## 5. Troubleshooting

If you encounter issues:

1. **High CPU Usage**
   - Decrease `target_cpu_usage`
   - Reduce `max_processors`

2. **Slow Processing**
   - Increase `min_batch_size`
   - Increase `concurrent_processors`

3. **High Memory Usage**
   - Decrease `max_batch_size`
   - Reduce `concurrent_processors`

## Need More Help?

- Check the full documentation in `docs/optimization/README.md`
- Review the monitoring dashboard
- Check the logs for optimization-related messages
