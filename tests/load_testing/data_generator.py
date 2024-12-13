"""Feed data generator for load testing."""
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Literal, TypedDict

class FeedItem(TypedDict):
    title: str
    content: str
    content_type: Literal["BLOG", "VIDEO", "SOCIAL"]
    priority: Literal["High", "Medium", "Low"]
    published_at: str
    url: str

class TestFeed(TypedDict):
    items: List[FeedItem]
    update_frequency: Literal["high", "medium", "low"]
    size: Literal["small", "medium", "large"]

def create_feed_item(
    title: str,
    content_type: Literal["BLOG", "VIDEO", "SOCIAL"],
    priority: Literal["High", "Medium", "Low"]
) -> FeedItem:
    """Create a single feed item for testing."""
    content_templates = {
        "BLOG": "This is a blog post about {topic} with {words} words...",
        "VIDEO": "Video content showcasing {topic} with duration {duration} minutes",
        "SOCIAL": "Social media update about {topic} with {engagement} interactions"
    }
    
    topics = ["technology", "science", "health", "business", "entertainment"]
    
    return {
        "title": title,
        "content": content_templates[content_type].format(
            topic=random.choice(topics),
            words=random.randint(100, 1000),
            duration=random.randint(1, 30),
            engagement=random.randint(10, 10000)
        ),
        "content_type": content_type,
        "priority": priority,
        "published_at": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat(),
        "url": f"https://example.com/content/{random.randint(1000, 9999)}"
    }

def generate_test_feed(
    size: Literal["small", "medium", "large"],
    content_type: Literal["BLOG", "VIDEO", "SOCIAL"]
) -> TestFeed:
    """Generate a complete test feed with specified characteristics."""
    size_ranges = {
        "small": (10, 50),
        "medium": (100, 500),
        "large": (1000, 2000)
    }
    
    update_frequencies = {
        "small": "high",
        "medium": "medium",
        "large": "low"
    }
    
    item_count = random.randint(*size_ranges[size])
    
    return {
        "items": [
            create_feed_item(
                title=f"Test Item {i}",
                content_type=content_type,
                priority=random.choice(["High", "Medium", "Low"])
            ) for i in range(item_count)
        ],
        "size": size,
        "update_frequency": update_frequencies[size]
    }

def simulate_load(feeds_per_minute: int, duration_seconds: int) -> None:
    """
    Simulate production load by generating and processing feeds at a specified rate.
    
    Args:
        feeds_per_minute: Number of feeds to generate per minute
        duration_seconds: How long to run the simulation in seconds
    """
    start_time = time.time()
    feeds_generated = 0
    
    while time.time() - start_time < duration_seconds:
        feed = generate_test_feed(
            size=random.choice(["small", "medium", "large"]),
            content_type=random.choice(["BLOG", "VIDEO", "SOCIAL"])
        )
        
        # In a real implementation, this would call the feed processor
        # process_feed(feed)
        
        feeds_generated += 1
        time.sleep(60 / feeds_per_minute)
        
        if feeds_generated % 100 == 0:
            print(f"Generated {feeds_generated} feeds...")
            
    print(f"Load simulation complete. Generated {feeds_generated} feeds in {duration_seconds} seconds")
