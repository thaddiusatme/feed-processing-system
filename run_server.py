"""Run the feed processing server."""

import time

from feed_processor.api import start_api_server
from feed_processor.processor import FeedProcessor

if __name__ == "__main__":
    # Start the server
    server = start_api_server(processor_instance=FeedProcessor())
    print("Server started on http://localhost:8000")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
