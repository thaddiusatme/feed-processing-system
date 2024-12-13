"""Integration tests for webhook delivery system."""
import pytest
from unittest.mock import patch
import requests
import time
from feed_processor import FeedProcessor
from feed_processor.webhook import WebhookManager

@pytest.fixture
def webhook_manager():
    return WebhookManager(
        webhook_url="http://localhost:8080/webhook",
        rate_limit=0.2,
        max_retries=3
    )

def test_rate_limiting(webhook_manager):
    """Test that webhook delivery respects rate limits."""
    start_time = time.time()
    
    # Send multiple requests
    for _ in range(5):
        webhook_manager.send({"test": "data"})
    
    end_time = time.time()
    duration = end_time - start_time
    
    # With rate limit of 0.2 req/s, 5 requests should take at least 20 seconds
    assert duration >= 20

def test_retry_mechanism(webhook_manager):
    """Test webhook retry mechanism with failing endpoint."""
    with patch('requests.post') as mock_post:
        # Make first two calls fail, third succeed
        mock_post.side_effect = [
            requests.exceptions.RequestException,
            requests.exceptions.RequestException,
            type('Response', (), {'status_code': 200})()
        ]
        
        # Send webhook
        result = webhook_manager.send({"test": "data"})
        
        # Verify retries
        assert mock_post.call_count == 3
        assert result.success

def test_circuit_breaker(webhook_manager):
    """Test circuit breaker prevents requests after failures."""
    with patch('requests.post') as mock_post:
        # Make all calls fail
        mock_post.side_effect = requests.exceptions.RequestException
        
        # Send multiple webhooks to trigger circuit breaker
        for _ in range(10):
            webhook_manager.send({"test": "data"})
        
        # Verify circuit breaker is open
        assert webhook_manager.circuit_breaker.is_open
        
        # Try one more request
        result = webhook_manager.send({"test": "data"})
        assert not result.success
        assert result.error == "Circuit breaker is open"
