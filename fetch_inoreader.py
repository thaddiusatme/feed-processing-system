"""Fetch feeds from InoReader and process them."""

import asyncio
import os

from dotenv import load_dotenv

from feed_processor.api import start_api_server
from feed_processor.content_queue import QueueItem
from feed_processor.inoreader.client import InoreaderClient, InoreaderConfig
from feed_processor.processor import FeedProcessor


async def main():
    # Load environment variables
    load_dotenv()

    # Read OAuth token
    with open("oauth_token.txt", "r") as f:
        token = f.read().strip()

    # Configure InoReader client
    config = InoreaderConfig(
        app_id=os.getenv("INOREADER_APP_ID"), api_key=os.getenv("INOREADER_API_KEY"), token=token
    )

    # Initialize client
    client = InoreaderClient(config)

    try:
        # Initialize session
        await client._init_session()

        # Fetch stream contents
        print("Fetching stream contents...")
        items = await client.get_stream_contents(count=50)  # Get last 50 items
        print(f"Found {len(items)} items")

        # Start feed processor
        processor = FeedProcessor(
            airtable_api_key=os.getenv("AIRTABLE_API_KEY"),
            airtable_base_id=os.getenv("AIRTABLE_BASE_ID"),
            airtable_table_id=os.getenv("AIRTABLE_TABLE_ID"),
            airtable_rate_limit=0.2,  # 5 requests per second
            airtable_batch_size=10,
        )

        # Start the processor
        await processor.start()
        print("Feed processor started with Airtable integration")

        # Start API server
        server = start_api_server(processor_instance=processor)

        # Process each item
        for item in items:
            print(f"Processing item: {item.title}")
            # Create queue item
            queue_item = QueueItem(
                id=str(asyncio.get_event_loop().time()),
                content={
                    "id": item.sourceMetadata.feedId,
                    "feed": {
                        "title": item.title,
                        "description": item.brief,
                        "link": item.sourceMetadata.originalUrl,
                        "pubDate": item.sourceMetadata.publishDate.isoformat(),
                        "author": item.sourceMetadata.author,
                        "tags": item.sourceMetadata.tags,
                    },
                },
                timestamp=asyncio.get_event_loop().time(),
            )
            # Queue item for processing
            await processor.queue.add(queue_item)

        print("All items queued, waiting for processing to complete...")

        # Wait for the queue to be empty
        while not processor.queue.empty():
            await asyncio.sleep(1)
            print(f"Items remaining in queue: {processor.queue.qsize()}")

        # Wait a bit more to ensure all items are processed
        await asyncio.sleep(5)
        print("Processing complete!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Stop the processor
        await processor.stop()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
