import requests
import time
from typing import Dict, List, Any
from datetime import datetime
from .rate_limiter import RateLimiter
from .processing_metrics import ProcessingMetrics
import logging
from typing import Optional, Callable
from functools import wraps

class FeedProcessingError(Exception):
    """Custom exception for feed processing errors"""
    pass

def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator that implements retry logic with exponential backoff
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for retry in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_exception = e
                    self.metrics.increment_errors()
                    
                    if retry < max_retries - 1:
                        logging.warning(f"Attempt {retry + 1} failed, retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    
            raise FeedProcessingError(f"Max retries exceeded: {str(last_exception)}")
        return wrapper
    return decorator

class FeedProcessor:
    """
    Main processor for handling feed content from Inoreader and delivering to webhook
    """
    def __init__(self, inoreader_token: str, webhook_url: str):
        self.inoreader_token = inoreader_token
        self.webhook_url = webhook_url
        self.rate_limiter = RateLimiter(min_interval=0.2)
        self.metrics = ProcessingMetrics()
    
    def fetch_feeds(self) -> List[Dict[str, Any]]:
        """
        Fetch feeds from Inoreader API
        """
        headers = {
            "Authorization": f"Bearer {self.inoreader_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://www.inoreader.com/reader/api/0/stream/contents/user/-/state/com.google/reading-list",
            headers=headers
        )
        
        if response.status_code != 200:
            self.metrics.increment_errors()
            raise FeedProcessingError(f"Failed to fetch feeds: {response.status_code}")
        
        return response.json()["items"]
    
    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single feed item into the required format
        """
        try:
            processed = {
                "title": item["title"],
                "contentType": "BLOG",  # Could be enhanced with content type detection
                "brief": self._generate_brief(item["content"]["content"]),
                "priority": self._calculate_priority(item),
                "sourceMetadata": {
                    "feedId": item["origin"]["streamId"],
                    "originalUrl": item.get("canonical", [None])[0],
                    "publishDate": datetime.fromtimestamp(item["published"]).isoformat(),
                    "author": item.get("author"),
                    "tags": item.get("categories", [])
                }
            }
            
            self.metrics.increment_processed()
            return processed
            
        except Exception as e:
            self.metrics.increment_errors()
            raise FeedProcessingError(f"Failed to process item: {str(e)}")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def send_to_webhook(self, data: Dict[str, Any]) -> bool:
        """
        Send processed data to webhook with rate limiting and retry logic
        """
        self.rate_limiter.wait()
        
        response = requests.post(
            self.webhook_url,
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise FeedProcessingError(f"Webhook delivery failed: {response.status_code}")
        
        return True
    
    def _generate_brief(self, content: str, max_length: int = 200) -> str:
        """
        Generate a brief summary of the content
        """
        # Simple implementation - could be enhanced with NLP
        return content[:max_length].strip() + "..."
    
    def _calculate_priority(self, item: Dict[str, Any]) -> str:
        """
        Calculate priority based on item attributes
        """
        # Simple implementation - could be enhanced with more sophisticated logic
        if "important" in item.get("categories", []):
            return "High"
        elif time.time() - item["published"] < 86400:  # Last 24 hours
            return "Medium"
        return "Low" 
    
    def process_feeds(self) -> None:
        """
        Main processing loop that fetches and processes all feeds
        """
        try:
            feeds = self.fetch_feeds()
            for item in feeds:
                try:
                    processed_item = self.process_item(item)
                    self.send_to_webhook(processed_item)
                except Exception as e:
                    logging.error(f"Failed to process item: {str(e)}")
                    self.metrics.increment_errors()
                    continue
        except Exception as e:
            logging.error(f"Failed to fetch feeds: {str(e)}")
            self.metrics.increment_errors()
            raise