#!/usr/bin/env python3
"""Test script to fetch feed items from InoReader."""

import asyncio
import os
from urllib.parse import quote

from dotenv import load_dotenv

from feed_processor.inoreader.client import InoreaderClient, InoreaderConfig


async def main():
    # Load environment variables
    load_dotenv()

    # Get the OAuth token from the previous run
    with open("oauth_token.txt", "r") as f:
        oauth_token = f.read().strip()

    # Create client config
    config = InoreaderConfig(
        app_id=os.getenv("INOREADER_APP_ID"),
        api_key=os.getenv("INOREADER_API_KEY"),
        token=oauth_token,  # Use the OAuth token from get_inoreader_token.py
    )

    # Create client
    client = InoreaderClient(config)

    try:
        # First get list of subscriptions
        print("\nFetching subscriptions...")
        subscriptions = await client.get_subscription_list()

        if not subscriptions:
            print("No subscriptions found!")
            return

        # Print subscriptions and let user choose one
        print("\nYour subscriptions:")
        for i, sub in enumerate(subscriptions):
            print(f"{i+1}. {sub['title']} ({sub['id']})")

        # Get first subscription's items as an example
        sub = subscriptions[0]
        feed_id = sub["id"]

        print(f"\nFetching items from: {sub['title']}")
        items = await client.get_stream_contents_by_stream_id(feed_id, count=10)

        print("\nLatest items:")
        for item in items:
            print(f"- {item.get('title', 'No title')} ({item.get('published', 'No date')})")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
