"""Locust load testing configuration for feed processing system."""
import json
import random
from locust import HttpUser, task, between
from data_generator import generate_test_feed

class FeedProcessingUser(HttpUser):
    """Simulates users sending feeds to the processing system."""
    
    # Wait between 1 and 5 seconds between tasks
    wait_time = between(1, 5)
    
    def on_start(self):
        """Initialize the user session."""
        # Configure base URLs for different services
        self.metrics_url = "http://localhost:49152"
        self.api_url = "http://localhost:8000"  # Default API port
    
    @task(3)  # Higher weight for small feeds
    def process_small_feed(self):
        """Submit a small feed for processing."""
        feed = generate_test_feed("small", random.choice(["BLOG", "VIDEO", "SOCIAL"]))
        self.client.post(f"{self.api_url}/process", json=feed)
    
    @task(2)  # Medium weight for medium feeds
    def process_medium_feed(self):
        """Submit a medium-sized feed for processing."""
        feed = generate_test_feed("medium", random.choice(["BLOG", "VIDEO", "SOCIAL"]))
        self.client.post(f"{self.api_url}/process", json=feed)
    
    @task(1)  # Lower weight for large feeds
    def process_large_feed(self):
        """Submit a large feed for processing."""
        feed = generate_test_feed("large", random.choice(["BLOG", "VIDEO", "SOCIAL"]))
        self.client.post(f"{self.api_url}/process", json=feed)
    
    @task(4)  # Highest weight for webhook status checks
    def check_webhook_status(self):
        """Check the status of webhook deliveries."""
        self.client.get(f"{self.api_url}/webhook/status")
    
    @task(2)
    def get_metrics(self):
        """Retrieve processing metrics."""
        self.client.get(f"{self.metrics_url}/metrics")
