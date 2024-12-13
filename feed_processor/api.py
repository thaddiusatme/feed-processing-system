"""API server for feed processing system."""
from flask import Flask, request, jsonify
from .processor import FeedProcessor
import threading

app = Flask(__name__)
processor = None

@app.route('/process', methods=['POST'])
def process_feed():
    """Process a feed."""
    try:
        feed = request.json
        if not feed:
            return jsonify({"error": "No feed data provided"}), 400
        
        # Add feed to processing queue
        processor.queue.put(feed)
        return jsonify({"status": "Feed queued for processing"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/status', methods=['GET'])
def webhook_status():
    """Get webhook delivery status."""
    try:
        if not processor.webhook_manager:
            return jsonify({"error": "Webhook manager not configured"}), 400
        
        status = {
            "queue_size": processor.queue.qsize(),
            "current_batch_size": len(processor.current_batch),
            "webhook_enabled": True
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_api_server(host='localhost', port=8000, processor_instance=None):
    """Start the API server."""
    global processor
    processor = processor_instance
    if not processor:
        raise ValueError("FeedProcessor instance must be provided")
    
    # Start Flask in a separate thread
    def run_flask():
        app.run(host=host, port=port)
    
    api_thread = threading.Thread(target=run_flask, daemon=True)
    api_thread.start()
    return api_thread
