"""API server for feed processing system."""

import asyncio
import threading
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from .content_queue import QueueItem
from .processor import FeedProcessor

app = Flask(__name__)
processor = None
server = None


def async_route(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()

    return wrapped


@app.route("/process", methods=["POST"])
@async_route
async def process_feed():
    """Process a feed."""
    try:
        feed = request.json
        if not feed:
            return jsonify({"error": "No feed data provided"}), 400

        # Create queue item
        item = QueueItem(
            id=str(feed.get("id", "unknown")),
            content=feed,
            timestamp=asyncio.get_event_loop().time(),
        )

        # Add feed to processing queue
        success = await processor.queue.add(item)

        if success:
            return jsonify({"status": "Feed queued for processing"}), 202
        else:
            return jsonify({"error": "Failed to queue feed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/webhook/status", methods=["GET"])
def webhook_status():
    """Get webhook delivery status."""
    try:
        if not processor.webhook_config:
            return jsonify({"error": "Webhook not configured"}), 400

        status = {
            "queue_size": processor.queue._size,
            "webhook_enabled": True,
            "webhook_url": processor.webhook_config.url,
            "webhook_batch_size": processor.webhook_config.batch_size,
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


class ServerThread(threading.Thread):
    def __init__(self, app, host, port):
        threading.Thread.__init__(self)
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def start_api_server(host="localhost", port=8000, processor_instance=None):
    """Start the API server."""
    global processor, server
    processor = processor_instance
    if not processor:
        raise ValueError("FeedProcessor instance must be provided")

    server = ServerThread(app, host, port)
    server.daemon = True
    server.start()
    return server


def stop_api_server():
    """Stop the API server."""
    global server
    if server:
        server.shutdown()
        server = None
