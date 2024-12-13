# Feed Processing System

A robust Python-based feed processing system that fetches, processes, and delivers content through webhooks. The system is designed to handle high-volume content processing with features like rate limiting, error handling, and content prioritization.

## Features

### Core Processing
- **Inoreader Integration**
  - Seamless integration with Inoreader API
  - Efficient pagination handling
  - Robust error handling for API interactions
  - Configurable batch sizes

- **Priority-Based Processing**
  - Three-level priority system (High, Normal, Low)
  - Breaking news detection
  - Time-based priority adjustment
  - Configurable priority rules

- **Queue Management**
  - Thread-safe priority queue implementation
  - Efficient O(1) operations with deque
  - Priority-based item displacement
  - Queue size monitoring

### Content Delivery
- **Webhook Management**
  - Rate-limited delivery system
  - Configurable retry mechanism
  - Exponential backoff for failures
  - Bulk sending capabilities

- **Error Handling**
  - Comprehensive error tracking
  - Circuit breaker pattern
  - Detailed error context
  - Error metrics collection

- **Logging and Monitoring**
  - Structured logging with structlog
  - Request lifecycle tracking
  - Performance metrics
  - Queue statistics

- **Metrics and Monitoring**
  - Counter metrics for tracking cumulative values
  - Gauge metrics for current state values
  - Histogram metrics for latency distributions
  - Thread-safe metric operations
  - Support for metric labels and timestamps
  - Prometheus and Grafana integration

## Quick Start

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/feed-processing-system.git
cd feed-processing-system
```

2. **Set up the environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start the monitoring stack**:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

5. **Run the processor**:
```python
from feed_processor import FeedProcessor

processor = FeedProcessor()
processor.start()
```

6. **Access monitoring**:
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

## Configuration

### Environment Variables

```env
# Core Configuration
INOREADER_TOKEN=your_api_token
WEBHOOK_URL=your_webhook_url

# Performance Tuning
WEBHOOK_RATE_LIMIT=0.2  # Requests per second
MAX_RETRIES=3
QUEUE_SIZE=1000
ERROR_HISTORY_SIZE=100

# Monitoring
METRICS_PORT=8000
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090
```

### Priority Rules

Customize priority rules by subclassing `FeedProcessor`:

```python
class CustomFeedProcessor(FeedProcessor):
    def _determine_priority(self, item: Dict[str, Any]) -> Priority:
        if self._is_breaking_news(item):
            return Priority.HIGH
        if self._is_from_trusted_source(item):
            return Priority.NORMAL
        return Priority.LOW
```

## Monitoring

### Available Metrics

#### Processing Metrics
- `feed_items_processed_total`: Counter of processed items
  - Labels: `status=[success|failure]`
- `feed_processing_latency_seconds`: Processing time histogram
- `feed_queue_size`: Current queue size by priority

#### Webhook Metrics
- `webhook_retries_total`: Retry attempts counter
  - Labels: `attempt=[1|2|3]`
- `webhook_duration_seconds`: Webhook latency histogram
- `webhook_payload_size_bytes`: Payload size histogram
- `rate_limit_delay_seconds`: Current rate limit delay gauge

#### Queue Metrics
- `queue_overflow_total`: Queue overflow counter
  - Labels: `priority=[high|medium|low]`
- `queue_items_by_priority`: Current items by priority

### Dashboard Features

The Grafana dashboard provides:

#### Performance Panels
- Processing success/failure rates
- Queue size with thresholds
- Latency trends
- Queue distribution

#### System Health Panels
- Webhook retry patterns
- Rate limiting impact
- Payload size trends
- Queue overflow events

Features:
- Real-time updates (5s refresh)
- Historical data viewing
- Interactive tooltips
- Statistical summaries

## Development

### Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest                    # All tests
python -m pytest tests/unit/        # Unit tests
python -m pytest tests/integration/ # Integration tests
python -m pytest --cov             # Coverage report
```

### Code Quality

```bash
# Format code
black .

# Type checking
mypy .

# Linting
flake8
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please use the GitHub issue tracker.
