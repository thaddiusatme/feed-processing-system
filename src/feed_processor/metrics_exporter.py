"""Prometheus metrics exporter for the feed processing system."""

import time
from typing import Dict, Any
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from prometheus_client.core import CollectorRegistry
import structlog

logger = structlog.get_logger(__name__)

class PrometheusExporter:
    """Export metrics in Prometheus format."""
    
    def __init__(self, port: int = 8000):
        """Initialize the Prometheus exporter.
        
        Args:
            port: Port to expose metrics on
        """
        self.port = port
        self.registry = CollectorRegistry()
        
        # Processing metrics
        self.items_processed = Counter(
            'feed_items_processed_total',
            'Total number of feed items processed',
            ['status'],
            registry=self.registry
        )
        self.queue_size = Gauge(
            'feed_queue_size',
            'Current size of the processing queue',
            ['priority'],
            registry=self.registry
        )
        self.processing_latency = Histogram(
            'feed_processing_latency_seconds',
            'Feed processing latency in seconds',
            registry=self.registry
        )
        
        # API metrics
        self.api_requests = Counter(
            'feed_api_requests_total',
            'Total number of API requests',
            ['status'],
            registry=self.registry
        )
        self.api_latency = Histogram(
            'feed_api_latency_seconds',
            'API request latency in seconds',
            registry=self.registry
        )
        
        # Webhook metrics
        self.webhook_requests = Counter(
            'feed_webhook_requests_total',
            'Total number of webhook requests',
            ['status'],
            registry=self.registry
        )
        self.webhook_retries = Counter(
            'feed_webhook_retries_total',
            'Total number of webhook retry attempts',
            registry=self.registry
        )
        self.webhook_latency = Histogram(
            'feed_webhook_latency_seconds',
            'Webhook request latency in seconds',
            registry=self.registry
        )
        self.rate_limit_delay = Gauge(
            'feed_rate_limit_delay_seconds',
            'Current rate limit delay in seconds',
            registry=self.registry
        )
        
        # Queue metrics
        self.queue_overflows = Counter(
            'feed_queue_overflows_total',
            'Total number of queue overflow events',
            ['priority'],
            registry=self.registry
        )
        self.enqueued_items = Counter(
            'feed_enqueued_items_total',
            'Total number of items enqueued',
            ['priority'],
            registry=self.registry
        )
        self.dequeued_items = Counter(
            'feed_dequeued_items_total',
            'Total number of items dequeued',
            registry=self.registry
        )
    
    def start(self):
        """Start the Prometheus HTTP server."""
        try:
            start_http_server(self.port, registry=self.registry)
            logger.info("prometheus_exporter_started", port=self.port)
        except Exception as e:
            logger.error("prometheus_exporter_failed", error=str(e))
            raise
    
    def update_from_snapshot(self, metrics_snapshot: Dict[str, Any]):
        """Update Prometheus metrics from a metrics snapshot.
        
        Args:
            metrics_snapshot: Snapshot from MetricsCollector
        """
        try:
            # Processing metrics
            if "items_processed" in metrics_snapshot:
                for label, value in metrics_snapshot["items_processed"]["labels"].items():
                    status = label.split("=")[1]
                    self.items_processed.labels(status=status)._value.set(value["value"])
            
            if "processing_latency" in metrics_snapshot:
                self.processing_latency.observe(metrics_snapshot["processing_latency"]["value"])
            
            # Queue metrics
            if "queue_size" in metrics_snapshot:
                for label, value in metrics_snapshot["queue_size"]["labels"].items():
                    priority = label.split("=")[1]
                    self.queue_size.labels(priority=priority).set(value["value"])
            
            # API metrics
            if "api_requests" in metrics_snapshot:
                for label, value in metrics_snapshot["api_requests"]["labels"].items():
                    status = label.split("=")[1]
                    self.api_requests.labels(status=status)._value.set(value["value"])
            
            if "api_latency" in metrics_snapshot:
                self.api_latency.observe(metrics_snapshot["api_latency"]["value"])
            
            # Webhook metrics
            if "webhook_requests" in metrics_snapshot:
                for label, value in metrics_snapshot["webhook_requests"]["labels"].items():
                    status = label.split("=")[1]
                    self.webhook_requests.labels(status=status)._value.set(value["value"])
            
            if "webhook_retries" in metrics_snapshot:
                self.webhook_retries._value.set(metrics_snapshot["webhook_retries"]["value"])
            
            if "webhook_latency" in metrics_snapshot:
                self.webhook_latency.observe(metrics_snapshot["webhook_latency"]["value"])
            
            if "rate_limit_delay" in metrics_snapshot:
                self.rate_limit_delay.set(metrics_snapshot["rate_limit_delay"]["value"])
            
            logger.debug("prometheus_metrics_updated")
        except Exception as e:
            logger.error("prometheus_metrics_update_failed", error=str(e))
            raise
