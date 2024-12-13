"""Integration tests for the monitoring system."""
import pytest
from prometheus_client.parser import text_string_to_metric_families
import requests
from feed_processor import FeedProcessor
from feed_processor.metrics_exporter import PrometheusExporter

@pytest.fixture
def feed_processor():
    return FeedProcessor()

@pytest.fixture
def metrics_exporter():
    exporter = PrometheusExporter(port=8000)
    exporter.start()
    yield exporter
    exporter.stop()

def test_metrics_exposure(feed_processor, metrics_exporter):
    """Test that metrics are properly exposed via HTTP."""
    # Process some items
    feed_processor.process_queue(batch_size=5)
    
    # Update metrics
    metrics_snapshot = feed_processor.metrics.get_snapshot()
    metrics_exporter.update_from_snapshot(metrics_snapshot)
    
    # Fetch metrics via HTTP
    response = requests.get("http://localhost:8000/metrics")
    assert response.status_code == 200
    
    # Parse metrics
    metrics = list(text_string_to_metric_families(response.text))
    
    # Verify essential metrics are present
    metric_names = {m.name for m in metrics}
    assert "feed_items_processed_total" in metric_names
    assert "feed_processing_latency_seconds" in metric_names
    assert "feed_queue_size" in metric_names

def test_grafana_dashboard_provisioning(metrics_exporter):
    """Test that Grafana can access the metrics."""
    # Verify Grafana is accessible
    response = requests.get("http://localhost:3000/api/health")
    assert response.status_code == 200
    
    # Verify Prometheus datasource is configured
    response = requests.get(
        "http://localhost:3000/api/datasources/name/prometheus",
        auth=("admin", "admin")
    )
    assert response.status_code == 200

def test_prometheus_scraping(feed_processor, metrics_exporter):
    """Test that Prometheus can scrape our metrics."""
    # Process some items to generate metrics
    feed_processor.process_queue(batch_size=5)
    
    # Update metrics
    metrics_snapshot = feed_processor.metrics.get_snapshot()
    metrics_exporter.update_from_snapshot(metrics_snapshot)
    
    # Verify Prometheus can scrape our target
    response = requests.get("http://localhost:9090/api/v1/targets")
    assert response.status_code == 200
    
    data = response.json()
    targets = data["data"]["activeTargets"]
    our_target = next(
        (t for t in targets if t["labels"].get("job") == "feed_processor"),
        None
    )
    assert our_target is not None
    assert our_target["health"] == "up"
