"""Command line interface for the feed processor."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import click

from feed_processor.api import APIServer
from feed_processor.config import Config
from feed_processor.metrics import print_metrics
from feed_processor.validator import FeedValidator


def load_config(config_path: Optional[Path] = None) -> Dict:
    """Load configuration from file or use defaults.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Dict containing the configuration settings.
    """
    default_config = {
        "max_queue_size": 1000,
        "webhook_url": None,
        "rate_limit": 0.2,
    }

    if config_path and config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            return {**default_config, **config}

    return default_config


def async_command(f):
    """Run a Click command asynchronously.

    Args:
        f: The function to wrap.

    Returns:
        Wrapped function that runs asynchronously.
    """

    @click.command()
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        try:
            return asyncio.run(f(*args, **kwargs))
        except Exception as e:
            logging.error(f"Error in async command: {e}")
            ctx.exit(1)

    return wrapper


def start_api(config: Config) -> None:
    """Start the API server.

    Args:
        config: Configuration object.

    Raises:
        Exception: If API server fails to start.
    """
    try:
        api = APIServer(config)
        api.start()
    except Exception as e:
        logging.error(f"Failed to start API server: {e}")
        raise


def metrics(config: Optional[Dict] = None) -> None:
    """Display current metrics.

    Args:
        config: Optional configuration dictionary.

    Raises:
        Exception: If metrics cannot be displayed.
    """
    try:
        print_metrics()
    except Exception as e:
        logging.error(f"Error displaying metrics: {e}")
        raise


def validate_webhook_url(url: str) -> bool:
    """Validate webhook URL format.

    Args:
        url: The webhook URL to validate.

    Returns:
        bool: True if URL is valid, False otherwise.
    """
    try:
        result = re.match(r"^https?://[^\s]+$", url)
        return bool(result)
    except Exception as e:
        logging.error(f"Error validating webhook URL: {e}")
        return False


@click.group()
def cli():
    """Feed Processing System CLI."""
    pass


@cli.command()
@click.argument("feed_file", type=click.Path(exists=True))
def validate(feed_file: str) -> None:
    """
    Validate a feed file.

    Args:
        feed_file: Path to the feed file to validate.

    Raises:
        Exception: If validation fails.
    """
    try:
        with open(feed_file) as f:
            feed_content = f.read()

        validator = FeedValidator()
        result = validator.validate(feed_content)

        if result.error_type == "critical":
            raise Exception("Critical validation error")
        elif result.error_type == "validation":
            raise Exception("Validation error")
        elif not result.is_valid or result.errors:
            raise Exception("Invalid feed")

        click.echo("Feed is valid")

    except Exception as e:
        logging.error(f"Error validating feed: {e}")
        raise


@cli.command()
@click.argument("endpoint")
@click.option("--token", help="Authentication token")
@click.option("--batch-size", type=int, default=10, help="Batch size for webhook delivery")
@click.option("--output", type=click.Path(), help="Output file for configuration")
def configure(endpoint: str, token: Optional[str], batch_size: int, output: Optional[str]) -> None:
    """
    Configure webhook settings.

    Args:
        endpoint: Webhook endpoint URL.
        token: Optional authentication token.
        batch_size: Batch size for webhook delivery.
        output: Optional output file for configuration.

    Raises:
        Exception: If configuration fails.
    """
    try:
        if not validate_webhook_url(endpoint):
            raise Exception("Invalid webhook URL")

        config = {
            "webhook_url": endpoint,
            "webhook_auth_token": token,
            "webhook_batch_size": batch_size,
        }

        if output:
            with open(output, "w") as f:
                json.dump(config, f, indent=2)
        else:
            click.echo(json.dumps(config, indent=2))

    except Exception as e:
        logging.error(f"Error configuring webhook: {e}")
        raise


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        logging.error(f"Error: {e}")
        raise
