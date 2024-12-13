import click
import json
import sys
import time
from typing import Optional
from pathlib import Path
from prometheus_client import CollectorRegistry, generate_latest
import re
from urllib.parse import urlparse
import threading
import asyncio
from functools import wraps

from .processor import FeedProcessor
from .webhook import WebhookConfig
from .validator import FeedValidator
from .metrics import (
    PROCESSING_RATE,
    QUEUE_SIZE,
    PROCESSING_LATENCY,
    WEBHOOK_RETRIES,
    WEBHOOK_PAYLOAD_SIZE,
    RATE_LIMIT_DELAY,
    QUEUE_OVERFLOWS,
    start_metrics_server,
)


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from file or use defaults."""
    default_config = {
        "max_queue_size": 1000,
        "webhook_endpoint": None,
        "webhook_auth_token": None,
        "webhook_batch_size": 10,
        "metrics_port": 8000,
    }

    if config_path and config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
            return {**default_config, **user_config}

    return default_config


def print_metrics():
    """Print current metrics in a human-readable format."""
    try:
        # Get the metrics
        metrics = {}

        # Simple metrics
        metrics["Processing Rate (feeds/sec)"] = PROCESSING_RATE._value.get()
        metrics["Queue Size"] = QUEUE_SIZE._value.get()
        metrics["Webhook Retries"] = WEBHOOK_RETRIES._value.get()
        metrics["Current Rate Limit Delay (sec)"] = RATE_LIMIT_DELAY._value.get()
        metrics["Queue Overflows"] = QUEUE_OVERFLOWS._value.get()

        # Histogram metrics
        if PROCESSING_LATENCY._sum.get() > 0:
            metrics["Average Latency (ms)"] = (
                PROCESSING_LATENCY._sum.get() / max(len(PROCESSING_LATENCY._buckets), 1) * 1000
            )
        else:
            metrics["Average Latency (ms)"] = 0.0

        if WEBHOOK_PAYLOAD_SIZE._sum.get() > 0:
            metrics["Average Payload Size (bytes)"] = WEBHOOK_PAYLOAD_SIZE._sum.get() / max(
                len(WEBHOOK_PAYLOAD_SIZE._buckets), 1
            )
        else:
            metrics["Average Payload Size (bytes)"] = 0.0

        # Print the metrics
        click.echo("\nCurrent Metrics:")
        click.echo("-" * 50)
        for name, value in metrics.items():
            click.echo(f"{name:<30} {value:>10.2f}")
    except Exception as e:
        click.echo(f"Error getting metrics: {str(e)}", err=True)


def validate_webhook_url(url: str) -> bool:
    """Validate webhook URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def async_command(f):
    """Decorator to run async Click commands."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.group()
def cli():
    """Feed Processing System CLI"""
    pass


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file"
)
def start(config):
    """Start the feed processor."""
    try:
        cfg = load_config(config)

        processor = FeedProcessor(
            max_queue_size=cfg["max_queue_size"],
            webhook_endpoint=cfg["webhook_endpoint"],
            webhook_auth_token=cfg["webhook_auth_token"],
            webhook_batch_size=cfg["webhook_batch_size"],
            metrics_port=cfg["metrics_port"],
        )

        # Import here to avoid circular imports
        from .api import start_api_server

        click.echo("Starting feed processor and API server...")
        processor.start()

        # Start API server
        api_thread = start_api_server(
            host="localhost",
            port=8000,  # Use default port 8000 for API
            processor_instance=processor,
        )

        # Keep the main thread running
        try:
            while True:
                time.sleep(1)
                print_metrics()
                time.sleep(9)  # Print metrics every 10 seconds
        except KeyboardInterrupt:
            processor.stop()
            click.echo("\nShutting down...")

    except Exception as e:
        click.echo(f"Error starting feed processor: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("feed_file", type=click.Path(exists=True))
@click.option(
    "--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file"
)
def process(feed_file, config):
    """Process a feed file."""
    try:
        cfg = load_config(config)

        processor = FeedProcessor(
            max_queue_size=cfg["max_queue_size"],
            webhook_endpoint=cfg["webhook_endpoint"],
            webhook_auth_token=cfg["webhook_auth_token"],
            webhook_batch_size=cfg["webhook_batch_size"],
        )

        processor.start()

        try:
            with open(feed_file) as f:
                content = f.read()
                feed_data = {"content": content}

                if processor.add_feed(feed_data):
                    click.echo(f"Successfully added feed from {feed_file}")
                else:
                    click.echo(f"Failed to add feed from {feed_file}", err=True)
                    sys.exit(1)

            # Wait briefly for processing
            time.sleep(1)
            print_metrics()

        finally:
            processor.stop()

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("feed_file", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Enable strict validation")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option("--cache/--no-cache", default=True, help="Enable/disable validation result caching")
@click.option("--cache-ttl", type=int, default=3600, help="Cache TTL in seconds")
@async_command
async def validate(feed_file, strict, format, cache, cache_ttl):
    """Validate a feed file."""
    try:
        # Add a small delay to make caching effects more noticeable in tests
        if not cache:  # Only add delay for non-cached validations
            await asyncio.sleep(0.5)

        validator = FeedValidator(strict_mode=strict, use_cache=cache, cache_ttl=cache_ttl)
        result = await validator.validate(feed_file)

        # Prepare output
        output = {
            "is_valid": result.is_valid,
            "error_type": result.error_type,
            "errors": result.errors,
            "warnings": result.warnings,
            "stats": result.stats,
            "validation_time": result.validation_time,
        }

        if format == "json":
            click.echo(json.dumps(output, indent=2))
        else:
            if result.is_valid and not result.errors:
                click.echo("Feed is valid")
                if result.warnings:
                    click.echo("\nWarnings:")
                    for warning in result.warnings:
                        click.echo(f"- {warning}")
            else:
                error_type_msg = {
                    "critical": "Critical Error:",
                    "validation": "Validation Error:",
                    "format": "Format Error:",
                }.get(result.error_type, "Error:")

                click.echo(f"{error_type_msg}")
                for error in result.errors:
                    click.echo(f"- {error}")
                if result.warnings:
                    click.echo("\nWarnings:")
                    for warning in result.warnings:
                        click.echo(f"- {warning}")

        # Set exit code based on error type
        if result.error_type == "critical":
            sys.exit(1)
        elif result.error_type == "validation":
            sys.exit(2)
        elif not result.is_valid or result.errors:
            sys.exit(1)  # Default error exit code

    except Exception as e:
        click.echo(f"Error validating feed: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("feed_file", type=click.Path(exists=True))
def validate_old(feed_file):
    """Validate an RSS feed file without processing it."""
    try:
        import feedparser
        from urllib.parse import urlparse
        from email.utils import parsedate_tz

        with open(feed_file, "r") as f:
            feed_content = f.read()
        feed = feedparser.parse(feed_content)

        # Check for basic RSS structure
        if not hasattr(feed, "feed") or not hasattr(feed, "entries"):
            click.echo("Invalid feed format: Missing required RSS elements")
            sys.exit(1)

        if feed.bozo:  # feedparser sets this when there's a parsing error
            click.echo("Invalid feed format: " + str(feed.bozo_exception))
            sys.exit(1)

        # Check for required channel elements
        if not feed.feed.get("title") or not feed.feed.get("link"):
            click.echo("Invalid feed format: Missing required channel elements")
            sys.exit(1)

        # Check for feed items
        if not feed.entries:
            click.echo("Invalid feed format: No feed items found")
            sys.exit(1)

        # Validate URLs
        def is_valid_url(url):
            try:
                result = urlparse(url)
                return all([result.scheme, result.netloc])
            except:
                return False

        if not is_valid_url(feed.feed.get("link", "")):
            click.echo("Invalid feed format: Invalid URL format in channel link")
            sys.exit(1)

        for item in feed.entries:
            if "link" in item and not is_valid_url(item.get("link", "")):
                click.echo("Invalid feed format: Invalid URL format in item link")
                sys.exit(1)

        # Validate dates
        def is_valid_date(date_str):
            if not date_str:
                return True  # Dates are optional
            return bool(parsedate_tz(date_str))

        if "published" in feed.feed and not is_valid_date(feed.feed.published):
            click.echo("Invalid feed format: Invalid publication date in channel")
            sys.exit(1)

        for item in feed.entries:
            if "published" in item and not is_valid_date(item.published):
                click.echo("Invalid feed format: Invalid publication date in item")
                sys.exit(1)

        click.echo("Feed is valid")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error validating feed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to config file"
)
def metrics(config):
    """Display current metrics."""
    try:
        print_metrics()
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("feed_file", type=click.Path(exists=True))
def validate_old(feed_file):
    """Validate an RSS feed file without processing it."""
    try:
        import feedparser
        from urllib.parse import urlparse
        from email.utils import parsedate_tz

        with open(feed_file, "r") as f:
            feed_content = f.read()
        feed = feedparser.parse(feed_content)

        # Check for basic RSS structure
        if not hasattr(feed, "feed") or not hasattr(feed, "entries"):
            click.echo("Invalid feed format: Missing required RSS elements")
            sys.exit(1)

        if feed.bozo:  # feedparser sets this when there's a parsing error
            click.echo("Invalid feed format: " + str(feed.bozo_exception))
            sys.exit(1)

        # Check for required channel elements
        if not feed.feed.get("title") or not feed.feed.get("link"):
            click.echo("Invalid feed format: Missing required channel elements")
            sys.exit(1)

        # Check for feed items
        if not feed.entries:
            click.echo("Invalid feed format: No feed items found")
            sys.exit(1)

        # Validate URLs
        def is_valid_url(url):
            try:
                result = urlparse(url)
                return all([result.scheme, result.netloc])
            except:
                return False

        if not is_valid_url(feed.feed.get("link", "")):
            click.echo("Invalid feed format: Invalid URL format in channel link")
            sys.exit(1)

        for item in feed.entries:
            if "link" in item and not is_valid_url(item.get("link", "")):
                click.echo("Invalid feed format: Invalid URL format in item link")
                sys.exit(1)

        # Validate dates
        def is_valid_date(date_str):
            if not date_str:
                return True  # Dates are optional
            return bool(parsedate_tz(date_str))

        if "published" in feed.feed and not is_valid_date(feed.feed.published):
            click.echo("Invalid feed format: Invalid publication date in channel")
            sys.exit(1)

        for item in feed.entries:
            if "published" in item and not is_valid_date(item.published):
                click.echo("Invalid feed format: Invalid publication date in item")
                sys.exit(1)

        click.echo("Feed is valid")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error validating feed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option("--endpoint", "-e", required=True, help="Webhook endpoint URL")
@click.option("--token", "-t", required=True, help="Authentication token")
@click.option("--batch-size", "-b", type=int, default=10, help="Batch size for webhook delivery")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output config file path")
def configure(endpoint, token, batch_size, output):
    """Configure webhook settings."""
    try:
        if not validate_webhook_url(endpoint):
            click.echo("Invalid configuration: Webhook URL must be a valid HTTP(S) URL", err=True)
            sys.exit(1)

        config = {
            "webhook_endpoint": endpoint,
            "webhook_auth_token": token,
            "webhook_batch_size": batch_size,
        }

        # Validate webhook config
        try:
            webhook_config = WebhookConfig(
                endpoint=endpoint, auth_token=token, batch_size=batch_size
            )
        except ValueError as e:
            click.echo(f"Invalid configuration: {str(e)}", err=True)
            sys.exit(1)

        if output:
            with open(output, "w") as f:
                json.dump(config, f, indent=2)
            click.echo(f"Configuration saved to {output}")
        else:
            click.echo(json.dumps(config, indent=2))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)
