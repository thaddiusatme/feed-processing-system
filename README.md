# Feed Processing System

A robust and scalable system for processing RSS/Atom feeds with webhook delivery capabilities.

## Features

- Queue-based feed processing with configurable size
- Webhook delivery with retry mechanism and rate limiting
- Batch processing support
- Real-time metrics monitoring
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

## Usage

### Command Line Interface

The system provides a CLI with the following commands:

1. Start the feed processor:
```bash
python -m feed_processor.cli start [--config CONFIG_FILE]
```

2. Process a single feed file:
```bash
python -m feed_processor.cli process FEED_FILE [--config CONFIG_FILE]
```

3. View current metrics:
```bash
python -m feed_processor.cli metrics [--config CONFIG_FILE]
```

4. Configure webhook settings:
```bash
python -m feed_processor.cli configure --endpoint URL --token TOKEN [--batch-size SIZE] [--output CONFIG_FILE]
```

5. Validate an RSS feed file:
```bash
python -m feed_processor.cli validate feed_file.xml
```
This command checks if the feed file is properly formatted and contains all required RSS elements.

### Validate Feed
To validate an RSS feed file before processing:
```bash
python -m feed_processor.cli validate feed_file.xml
```

The validate command performs comprehensive checks on your RSS feed:
- Basic RSS structure and required elements
- Presence of feed items
- URL format validation for all links
- Publication date format validation
- Required channel elements (title, link)

For stricter validation, use the `--strict` flag:
```bash
python -m feed_processor.cli validate --strict feed_file.xml
```

Strict mode enforces additional rules:
- UTF-8 encoding requirement
- Maximum content lengths:
  - Titles: 200 characters
  - Descriptions: 5000 characters
- Required recommended elements (descriptions)

If any issues are found, the command will exit with status code 1 and display a specific error message.

### Feed Validation

The system includes a robust feed validation command that checks RSS feeds for validity and conformance to best practices:

```bash
# Basic validation
python -m feed_processor.cli validate feed.xml

# Strict validation with additional checks
python -m feed_processor.cli validate --strict feed.xml
```

### Validation Checks

#### Basic Mode
- RSS structure and required elements
- Channel elements (title, link)
- Feed items presence
- URL format validation
- Publication date format validation

#### Strict Mode
Additional checks in strict mode:
- UTF-8 encoding requirement
- Content length limits:
  - Titles: 200 characters
  - Descriptions: 5000 characters
- Required recommended elements (descriptions)

### Configuration

Create a JSON configuration file with the following structure:

```json
{
  "max_queue_size": 1000,
  "webhook_endpoint": "https://your-webhook.com/endpoint",
  "webhook_auth_token": "your-auth-token",
  "webhook_batch_size": 10,
  "metrics_port": 8000
}
```

### Metrics

The system exports the following Prometheus metrics:

- Processing Rate (feeds/sec)
- Queue Size
- Average Processing Latency (ms)
- Webhook Retries
- Average Payload Size (bytes)
- Rate Limit Delay (sec)
- Queue Overflows

## Project Structure

### Current Structure
```
feed_processor/
├── __init__.py
├── api.py                # API endpoints and interfaces
├── cli.py               # Command-line interface
├── content_analysis.py  # Content analysis functionality
├── content_queue.py     # Content-specific queue implementation
├── error_handling.py    # Error handling and circuit breaker
├── metrics.py          # Core metrics functionality
├── priority_queue.py   # Base priority queue implementation
├── processing_metrics.py # Processing-specific metrics
├── processor.py        # Main feed processor implementation
├── validator.py        # Core validation functionality
├── validators.py       # Extended validation rules
└── webhook.py         # Webhook handling and delivery

docs/                  # Documentation
├── api/              # API documentation
└── examples/         # Usage examples

tests/                # Test suite
├── unit/            # Unit tests
├── integration/     # Integration tests
└── fixtures/        # Test fixtures

monitoring/          # Monitoring configuration
└── prometheus/      # Prometheus configuration

scripts/             # Utility scripts
```

### Planned Structure (In Progress)
```
feed_processor/
├── config/                  # Configuration management
│   ├── __init__.py
│   ├── webhook_config.py    # Webhook-specific configuration
│   └── processor_config.py  # Core processor configuration
├── core/                    # Core processing logic
│   ├── __init__.py
│   └── processor.py        # Main feed processing implementation
├── queues/                 # Queue implementations
│   ├── __init__.py
│   ├── base.py            # Base queue implementations including PriorityQueue
│   └── content.py         # Content-specific queue implementations
├── metrics/               # Metrics and monitoring
│   ├── __init__.py
│   ├── prometheus.py      # Prometheus metrics integration
│   └── performance.py     # Performance monitoring metrics
├── validation/           # Feed validation
│   ├── __init__.py
│   └── validators.py     # Feed validation logic
├── webhook/             # Webhook handling
│   ├── __init__.py
│   └── manager.py      # Webhook delivery management
└── errors.py           # Centralized error handling
```

### Additional Project Files
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies
- `setup.py` - Package installation configuration
- `pyproject.toml` - Project metadata and build configuration
- `docker-compose.yml` - Docker services configuration
- `docker-compose.monitoring.yml` - Monitoring stack configuration
- `.env.example` - Example environment variables
- `Makefile` - Development and deployment commands

## Architecture Overview

The Feed Processing System is built with a modular architecture that separates concerns into distinct components:

#### 1. Core Processing (core/)
- `processor.py`: Implements the main feed processing logic
- Handles the orchestration of feed parsing, validation, and delivery
- Manages the lifecycle of feed processing jobs

#### 2. Queue Management (queues/)
- `base.py`: Contains the base `PriorityQueue` implementation for efficient job scheduling
- `content.py`: Extends the base queue with content-specific functionality
- Provides thread-safe operations for concurrent processing

#### 3. Configuration (config/)
- `webhook_config.py`: Manages webhook-related settings (endpoints, authentication, retry policies)
- `processor_config.py`: Controls core processor behavior (queue sizes, batch settings)
- Centralizes all configuration management

#### 4. Validation (validation/)
- `validators.py`: Implements comprehensive feed validation
- Supports both basic and strict validation modes
- Ensures feed quality and conformance to standards

#### 5. Webhook Delivery (webhook/)
- `manager.py`: Handles reliable webhook delivery
- Implements retry logic and rate limiting
- Manages batch processing of notifications

#### 6. Metrics and Monitoring (metrics/)
- `prometheus.py`: Exports Prometheus-compatible metrics
- `performance.py`: Tracks system performance metrics
- Provides real-time monitoring capabilities

#### 7. Error Handling (errors.py)
- Centralizes error definitions
- Implements custom exceptions for different failure scenarios
- Provides consistent error handling across components

### Component Interactions

1. **Feed Processing Flow**:
   - Incoming feeds → Validation → Queue → Processing → Webhook Delivery
   - Each step is monitored and metrics are collected

2. **Configuration Management**:
   - Components read from centralized configuration
   - Runtime configuration changes are supported

3. **Error Handling**:
   - Consistent error propagation
   - Automatic retry mechanisms
   - Detailed error reporting

4. **Monitoring**:
   - Real-time metrics collection
   - Performance monitoring
   - Health checks and alerts

### Design Principles

1. **Modularity**: Each component is self-contained and independently testable
2. **Scalability**: Queue-based architecture allows for horizontal scaling
3. **Reliability**: Comprehensive error handling and retry mechanisms
4. **Observability**: Detailed metrics and monitoring capabilities

## Best Practices and Guidelines

### Development Guidelines
1. **Code Organization**
   - Keep modules independent to avoid circular dependencies
   - Follow the planned directory structure for new code
   - Use appropriate error categories for proper monitoring

2. **Testing**
   - Mirror test files with source code structure
   - Include both unit and integration tests
   - Use provided test fixtures for consistency
   - Mock external services in tests

3. **Performance Considerations**
   - Use batch operations where possible
   - Monitor queue sizes in production
   - Set appropriate `max_size` values for queues
   - Respect rate limits of external services

### Operational Guidelines

1. **Logging Levels**
   - `ERROR`: Failures requiring immediate attention
   - `WARNING`: Unusual but handled situations
   - `INFO`: Normal operation events
   - `DEBUG`: Detailed troubleshooting

2. **Key Metrics**
   - Processing Rate (feeds/sec)
   - Queue Size and Memory Usage
   - Webhook Delivery Success Rate
   - Error Rates by Category
   - Rate Limit Delays

3. **Common Pitfalls**
   - Always validate content type before processing
   - Don't bypass validation checks
   - Configure rate limits based on external service documentation
   - Never commit sensitive values in configuration

4. **Environment Setup**
   - Use `.env` for local development
   - Reference `env.example` for required variables
   - Ensure webhook settings are properly configured
   - Validate auth tokens format

For more detailed information about lessons learned and best practices, see `LESSONS_LEARNED.md`.

## Development

### Setting Up Development Environment

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Run tests:
```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and ensure they pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
