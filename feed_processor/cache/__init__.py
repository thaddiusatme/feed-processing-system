"""Content caching package for feed processing system.

This package provides caching functionality with:
- LRU eviction policy
- TTL support
- Content compression
- Metrics tracking
"""

from feed_processor.cache.content_cache import CacheConfig, CacheEntry, ContentCache

__all__ = ["CacheConfig", "CacheEntry", "ContentCache"]
