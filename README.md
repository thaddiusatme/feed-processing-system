# Feed Processing System

A robust and scalable system for processing RSS/Atom feeds with webhook delivery capabilities.

## Features

- Queue-based feed processing with configurable size and priority
- Webhook delivery with:
  - Configurable retry mechanism
  - Rate limiting and batch processing
  - Circuit breaker pattern
- Metrics and monitoring:
  - Prometheus integration
  - Performance tracking
  - Custom dashboards
- Error handling:
  - Centralized error definitions
  - Automatic retry policies
  - Error categorization and tracking
- Modular architecture:
  - Dedicated configuration management
  - Pluggable queue implementations
  - Extensible validation system
- Batch processing support
- Real-time metrics monitoring with Prometheus integration
- Configurable webhook settings
- Thread-safe implementation
- Graceful shutdown handling
- Advanced error handling:
  - Circuit breaker pattern for service protection
  - Error tracking and metrics
  - Configurable error history
  - Sensitive data sanitization
  - Comprehensive error categorization

## Requirements

- Python 3.12+
- pip for package management

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/feed-processing-system.git
cd feed-processing-system
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure

```
feed_processor/
├── config/          # Configuration management
│   ├── webhook_config.py
│   └── processor_config.py
├── core/           # Core processing logic
│   └── processor.py
├── queues/         # Queue implementations
│   ├── base.py
│   └── content.py
├── metrics/        # Metrics collection
│   ├── prometheus.py
│   └── performance.py
├── validation/     # Input validation
│   └── validators.py
├── webhook/        # Webhook handling
│   └── manager.py
└── errors.py       # Error definitions
```

## Usage

### Quick Start

1. Start the feed processor:
```bash
python -m feed_processor start
```

2. Process a specific feed:
```bash
python -m feed_processor process --feed-url https://example.com/feed.xml
```

3. View current metrics:
```bash
python -m feed_processor metrics
```

### Configuration

Core settings are managed through environment variables or config files:

```bash
# Required settings
WEBHOOK_URL=https://api.example.com/webhook
WEBHOOK_TOKEN=your_token
MAX_QUEUE_SIZE=1000

# Optional settings
BATCH_SIZE=50
RETRY_COUNT=3
RATE_LIMIT=100
```

For detailed configuration options, see `config/` directory.

## Development

### Testing

Run the test suite:
```bash
pytest
```

For integration tests:
```bash
pytest tests/integration
```

### Metrics

The system exposes metrics via Prometheus at `/metrics`. Available metrics include:
- Queue size and processing rates
- Webhook delivery statistics
- Error rates and types
- Processing latency

### Configuration

Configuration is managed through dedicated modules in the `config/` directory:
- `webhook_config.py`: Webhook delivery settings
- `processor_config.py`: Core processor settings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and ensure they pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
