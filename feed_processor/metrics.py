"""Metrics collection and exposure for the feed processing system."""
import threading
import time
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import psutil
import structlog

logger = structlog.get_logger(__name__)

# Metrics definitions
QUEUE_SIZE = Gauge('feed_processor_queue_size', 'Current size of the processing queue')
PROCESSING_TIME = Histogram('feed_processor_processing_time_seconds',
                          'Time spent processing feeds',
                          buckets=(0.1, 0.5, 1.0, 2.0, 5.0))
MEMORY_USAGE = Gauge('feed_processor_memory_usage_bytes', 'Current memory usage')
CPU_USAGE = Gauge('feed_processor_cpu_usage_percent', 'Current CPU usage percentage')
FEEDS_PROCESSED = Counter('feed_processor_feeds_total', 'Total number of feeds processed')
ERRORS = Counter('feed_processor_errors_total', 'Total number of processing errors')


class MetricsServer:
    """Server for collecting and exposing metrics."""
    
    def __init__(self, port=8080):
        """Initialize metrics server.
        
        Args:
            port (int): Port to expose metrics on
        """
        self.port = port
        self._running = False
        self._thread = None
    
    def start(self):
        """Start the metrics server and collection thread."""
        try:
            start_http_server(self.port)
            logger.info("Started metrics server", port=self.port)
            
            self._running = True
            self._thread = threading.Thread(target=self._collect_metrics)
            self._thread.daemon = True
            self._thread.start()
            
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e))
            raise
    
    def stop(self):
        """Stop the metrics collection thread."""
        self._running = False
        if self._thread:
            self._thread.join()
    
    def _collect_metrics(self):
        """Collect system metrics periodically."""
        while self._running:
            try:
                # Update system metrics
                process = psutil.Process()
                
                # Memory usage
                mem_info = process.memory_info()
                MEMORY_USAGE.set(mem_info.rss)
                
                # CPU usage
                cpu_percent = process.cpu_percent(interval=1.0)
                CPU_USAGE.set(cpu_percent)
                
                time.sleep(5)  # Collect every 5 seconds
                
            except Exception as e:
                logger.error("Error collecting metrics", error=str(e))
                ERRORS.inc()
    
    def record_queue_size(self, size):
        """Record the current queue size.
        
        Args:
            size (int): Current size of the queue
        """
        QUEUE_SIZE.set(size)
    
    def record_processing_time(self, duration):
        """Record the time taken to process a feed.
        
        Args:
            duration (float): Processing time in seconds
        """
        PROCESSING_TIME.observe(duration)
        FEEDS_PROCESSED.inc()
    
    def record_error(self):
        """Record a processing error."""
        ERRORS.inc()
