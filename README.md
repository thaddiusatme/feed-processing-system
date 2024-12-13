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

```
feed_processor/
├── config/          # Configuration management
├── core/            # Core processing logic
├── queues/          # Queue implementations
├── metrics/         # Metrics and monitoring
├── validation/      # Feed validation
├── webhook/         # Webhook handling
└── errors.py        # Centralized error handling
```

### Key Components

- **Config**: Centralized configuration management for all components
- **Core**: Main processing logic and orchestration
- **Queues**: Priority-based queue system with content-specific implementations
- **Metrics**: Prometheus metrics and performance monitoring
- **Validation**: Feed validation and verification
- **Webhook**: Webhook delivery and management
- **Errors**: Unified error handling system

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
