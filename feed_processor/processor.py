import time
from queue import Queue, Full
from threading import Thread
from typing import Dict, Any
import json

from .metrics import (
    PROCESSING_RATE,
    QUEUE_SIZE,
    PROCESSING_LATENCY,
    WEBHOOK_RETRIES,
    WEBHOOK_PAYLOAD_SIZE,
    RATE_LIMIT_DELAY,
    QUEUE_OVERFLOWS,
    QUEUE_DISTRIBUTION,
    init_metrics
)
from .validators import FeedValidator

class FeedProcessor:
    def __init__(self, max_queue_size: int = 1000):
        self.queue = Queue(maxsize=max_queue_size)
        self.running = True
        self.processing_thread = Thread(target=self._process_queue, daemon=True)
        init_metrics()  # Initialize Prometheus metrics

    def start(self):
        """Start the feed processor."""
        self.processing_thread.start()

    def stop(self):
        """Stop the feed processor."""
        self.running = False
        if self.processing_thread.is_alive():
            self.processing_thread.join()

    def add_feed(self, feed_data: Dict[str, Any]) -> bool:
        """Add a feed to the processing queue."""
        # Validate the feed first
        validation_result = FeedValidator.validate_feed(feed_data.get('content', ''))
        if not validation_result.is_valid:
            return False

        try:
            self.queue.put(validation_result.parsed_feed, block=False)
            QUEUE_SIZE.set(self.queue.qsize())
            QUEUE_DISTRIBUTION.labels(
                feed_type=validation_result.feed_type
            ).inc()
            return True
        except Full:
            QUEUE_OVERFLOWS.inc()
            return False

    def _process_queue(self):
        """Process items from the queue."""
        while self.running:
            try:
                if not self.queue.empty():
                    feed_data = self.queue.get()
                    start_time = time.time()
                    
                    # Process the feed
                    self._process_feed(feed_data)
                    
                    # Record metrics
                    PROCESSING_RATE.inc()
                    PROCESSING_LATENCY.observe(time.time() - start_time)
                    QUEUE_SIZE.set(self.queue.qsize())
                    
                    # Update queue distribution
                    QUEUE_DISTRIBUTION.labels(
                        feed_type=feed_data.get('type', 'unknown')
                    ).dec()
                
                else:
                    time.sleep(0.1)  # Prevent busy waiting
            
            except Exception as e:
                print(f"Error processing feed: {str(e)}")

    def _process_feed(self, feed_data: Dict[str, Any]):
        """Process a single feed entry."""
        # Simulate processing delay
        time.sleep(0.1)
        
        # Record webhook payload size
        payload_size = len(json.dumps(feed_data))
        WEBHOOK_PAYLOAD_SIZE.observe(payload_size)
        
        # Simulate rate limiting
        if payload_size > 5000:
            delay = 0.5
            RATE_LIMIT_DELAY.set(delay)
            time.sleep(delay)
        else:
            RATE_LIMIT_DELAY.set(0)

        # Simulate webhook retries
        if payload_size > 10000:
            WEBHOOK_RETRIES.inc()
