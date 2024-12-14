"""CLI command for running the feed collector."""
import asyncio
import os
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

from feed_processor.core.feed_collector import FeedCollector, FeedCollectorConfig
from feed_processor.inoreader.client import InoreaderConfig
from feed_processor.storage.sqlite_storage import SQLiteConfig

logger = structlog.get_logger(__name__)


def async_command(f):
    """Decorator to run async Click commands."""

    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return asyncio.run(f(ctx, *args, **kwargs))

    return wrapper


@click.command()
@click.option(
    "--api-token",
    envvar="INOREADER_TOKEN",
    help="Inoreader API token",
    required=True,
)
@click.option(
    "--app-id",
    envvar="INOREADER_APP_ID",
    help="Inoreader App ID",
    required=True,
)
@click.option(
    "--api-key",
    envvar="INOREADER_API_KEY",
    help="Inoreader API Key",
    required=True,
)
@click.option(
    "--db-path",
    envvar="DATABASE_PATH",
    default="./data/feeds.db",
    help="Path to SQLite database",
    type=click.Path(),
)
@click.option(
    "--interval",
    envvar="COLLECTION_INTERVAL",
    default=60.0,
    help="Collection interval in seconds",
    type=float,
)
@async_command
async def collect(ctx, api_token: str, app_id: str, api_key: str, db_path: str, interval: float):
    """Run the feed collector."""
    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Initializing feed collector",
        token_length=len(api_token) if api_token else 0,
        app_id_length=len(app_id) if app_id else 0,
        api_key_length=len(api_key) if api_key else 0,
    )

    config = FeedCollectorConfig(
        inoreader=InoreaderConfig(token=api_token, app_id=app_id, api_key=api_key),
        storage=SQLiteConfig(db_path=db_path),
        collection_interval=interval,
    )

    collector = FeedCollector(config)

    try:
        await collector.start()
    except KeyboardInterrupt:
        logger.info("Stopping feed collector")
        collector.stop()


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    collect()
