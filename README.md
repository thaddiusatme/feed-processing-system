# Feed Processing System

A robust and scalable system for processing RSS/Atom feeds with webhook delivery capabilities.

## Features

- Queue-based feed processing with configurable size and priority
- Asynchronous API server with:
  - Thread-safe operations
  - Proper async/await support
  - Graceful shutdown handling
  - Enhanced error reporting
- Webhook delivery with:
  - Configurable retry mechanism
  - Rate limiting and batch processing
  - Circuit breaker pattern
- Advanced Performance Optimization:
  - Dynamic batch sizing and thread management
  - Intelligent resource allocation
  - Real-time performance monitoring
  - Adaptive processing parameters
- Metrics and monitoring:
  - Prometheus integration
  - Performance tracking
  - Custom dashboards
  - Resource utilization monitoring
- Error handling:
  - Centralized error definitions
  - Automatic retry policies
  - Error categorization and tracking
- Modular architecture:
  - Dedicated configuration management
  - Pluggable queue implementations
  - Extensible validation system
- SQLite Database Integration:
  - Persistent storage of feed items
  - Tag-based organization
  - Efficient querying and retrieval
  - Automatic schema management
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
- Google Drive Integration
  - Automated folder structure creation
  - Standardized content organization
  - Metadata tracking
- Webhook Processing
  - Rate-limited API endpoints
  - Data validation
  - Error handling

## Requirements

- Python 3.12+
- pip for package management

## Setup and Installation

1. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Google Drive credentials:
   - Create a project in Google Cloud Console
   - Enable Google Drive API
   - Create OAuth 2.0 credentials
   - Save credentials to `.env` file (see `.env.example`)

4. Run tests:
```bash
pytest
```

## Project Structure

```
feed_processor/
├── config/          # Configuration management
│   ├── webhook_config.py
│   └── processor_config.py
├── core/           # Core processing logic
│   ├── processor.py
│   └── database.py
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
DB_PATH=feeds.db
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

## Pipelines

### Inoreader to Airtable Pipeline

The system includes a dedicated pipeline for fetching content from Inoreader and storing it in Airtable. This pipeline:
- Fetches content from Inoreader using their API
- Processes and validates the content
- Stores the processed content in Airtable
- Includes comprehensive metrics and monitoring

To run the pipeline:

1. Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
# Edit .env with your Inoreader and Airtable credentials
```

2. Run the pipeline:
```bash
python run_pipeline.py
```

The pipeline will:
- Start a Prometheus metrics server (default port: 9090)
- Continuously fetch new content from Inoreader
- Process content in configurable batch sizes
- Store processed content in Airtable
- Provide real-time metrics and monitoring

Configuration options (via environment variables):
- `BATCH_SIZE`: Number of items to process in each batch (default: 50)
- `FETCH_INTERVAL`: Time in seconds between fetch operations (default: 60.0)
- `METRICS_PORT`: Port for Prometheus metrics server (default: 9090)
- `DB_PATH`: Path to SQLite database file (default: feeds.db)

Monitor the pipeline using:
- Prometheus metrics at http://localhost:9090
- Structured logs in JSON format
- Airtable dashboard for stored content

## Documentation

### Core Documentation
- [Installation and Setup](docs/setup/README.md)
- [Configuration Guide](docs/config/README.md)
- [API Reference](docs/api/README.md)

### Performance Optimization
- [Optimization Overview](docs/optimization/README.md)
- [Quick Start Guide](docs/optimization/QUICK_START.md)
- [System Diagrams](docs/optimization/DIAGRAMS.md)
- [Advanced Diagrams](docs/optimization/ADVANCED_DIAGRAMS.md)
- [Animated Workflows](docs/optimization/ANIMATED_WORKFLOWS.md)
- [Metrics Visualization](docs/optimization/METRICS_VISUALIZATION.md)

### Monitoring
- [Metrics Reference](docs/metrics/README.md)
- [Dashboard Setup](docs/monitoring/DASHBOARDS.md)
- [Alert Configuration](docs/monitoring/ALERTS.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and ensure they pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
