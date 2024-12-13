import time
from queue import Queue, Full
from threading import Thread, Event
from typing import Dict, Any, Optional, List
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
from .webhook import WebhookManager, WebhookConfig, WebhookResponse

class FeedProcessor:
    def __init__(self, 
                 max_queue_size: int = 1000,
                 webhook_endpoint: Optional[str] = None,
                 webhook_auth_token: Optional[str] = None,
                 webhook_batch_size: int = 10):
        self.queue = Queue(maxsize=max_queue_size)
        self._running = False
        self._stop_event = Event()
        self.processing_thread = None
        
        # Initialize webhook manager if endpoint is provided
        self.webhook_manager = None
        if webhook_endpoint and webhook_auth_token:
            webhook_config = WebhookConfig(
                endpoint=webhook_endpoint,
                auth_token=webhook_auth_token,
                batch_size=webhook_batch_size
            )
            self.webhook_manager = WebhookManager(webhook_config)
        
        # Initialize batch processing
        self.batch_size = webhook_batch_size
        self.current_batch: List[Dict[str, Any]] = []
        
        init_metrics()  # Initialize Prometheus metrics

    def start(self):
        """Start the feed processor."""
        if not self._running:
            self._running = True
            self._stop_event.clear()
            self.processing_thread = Thread(target=self._process_queue, daemon=True)
            self.processing_thread.start()

    def stop(self):
        """Stop the feed processor."""
        if self._running:
            self._running = False
            self._stop_event.set()
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=1)
            
            # Process any remaining items in the batch
            if self.current_batch:
                self._send_batch(self.current_batch)

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
        while self._running and not self._stop_event.is_set():
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
                    # If we have a partial batch and queue is empty, send it
                    if self.current_batch:
                        self._send_batch(self.current_batch)
                        self.current_batch = []
                    time.sleep(0.1)  # Prevent busy waiting
            
            except Exception as e:
                print(f"Error processing feed: {str(e)}")

    def _process_feed(self, feed_data: Dict[str, Any]):
        """Process a single feed entry."""
        # Record webhook payload size
        payload_size = len(json.dumps(feed_data))
        WEBHOOK_PAYLOAD_SIZE.observe(payload_size)
        
        # Add to current batch
        self.current_batch.append(feed_data)
        
        # Send batch if it reaches the batch size
        if len(self.current_batch) >= self.batch_size:
            self._send_batch(self.current_batch)
            self.current_batch = []

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send a batch of feeds to the webhook endpoint."""
        if not self.webhook_manager:
            return
            
        try:
            responses = self.webhook_manager.batch_send(batch)
            
            for response in responses:
                # Update metrics based on webhook response
                if not response.success:
                    WEBHOOK_RETRIES.inc(response.retry_count)
                    if response.rate_limited:
                        delay = float(response.error_message.split()[-1])
                        RATE_LIMIT_DELAY.set(delay)
                    else:
                        RATE_LIMIT_DELAY.set(0)
                else:
                    RATE_LIMIT_DELAY.set(0)
                    
        except Exception as e:
            print(f"Error sending webhook batch: {str(e)}")
            WEBHOOK_RETRIES.inc()
