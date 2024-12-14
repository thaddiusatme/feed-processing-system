#!/usr/bin/env python3
"""Script to run the Inoreader to Airtable pipeline."""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

import structlog
from prometheus_client import start_http_server

from feed_processor.core.clients import InoreaderClient
from feed_processor.pipeline import InoreaderToAirtablePipeline
from feed_processor.queues.content import ContentQueue
from feed_processor.storage import AirtableClient, AirtableConfig

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger(__name__)

# Global pipeline instance for graceful shutdown
pipeline: Optional[InoreaderToAirtablePipeline] = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    if pipeline:
        logger.info("shutdown_signal_received", signal=signum)
        pipeline.stop()


async def main():
    """Run the pipeline."""
    global pipeline

    try:
        # Start Prometheus metrics server
        metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        start_http_server(metrics_port)
        logger.info("metrics_server_started", port=metrics_port)

        # Initialize clients
        inoreader_client = InoreaderClient(
            client_id=os.environ["INOREADER_CLIENT_ID"],
            client_secret=os.environ["INOREADER_CLIENT_SECRET"],
            refresh_token=os.environ["INOREADER_REFRESH_TOKEN"],
        )

        airtable_config = AirtableConfig(
            api_key=os.environ["AIRTABLE_API_KEY"],
            base_id=os.environ["AIRTABLE_BASE_ID"],
            table_name=os.environ["AIRTABLE_TABLE_NAME"],
        )
        airtable_client = AirtableClient(airtable_config)

        # Initialize and run pipeline
        content_queue = ContentQueue()
        pipeline = InoreaderToAirtablePipeline(
            inoreader_client=inoreader_client,
            airtable_client=airtable_client,
            content_queue=content_queue,
            batch_size=int(os.getenv("BATCH_SIZE", "50")),
        )

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run pipeline with configured interval
        interval = float(os.getenv("FETCH_INTERVAL", "60.0"))
        await pipeline.run(interval=interval)

    except Exception as e:
        logger.error("pipeline_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
