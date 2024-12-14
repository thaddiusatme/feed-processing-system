"""Content cache implementation for feed processing system.

This module provides a thread-safe content caching system with:
- LRU eviction policy
- TTL support for cache entries
- Content compression using zlib
- Comprehensive metrics tracking
"""

import json
import threading
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from feed_processor.metrics import metrics


@dataclass
class CacheConfig:
    """Configuration for the content cache.

    Attributes:
        max_size: Maximum number of items to store in cache
        ttl_seconds: Time-to-live in seconds for cache entries
        enable_compression: Whether to compress cached content
    """

    max_size: int
    ttl_seconds: int
    enable_compression: bool = True


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata.

    Attributes:
        content: The cached content
        timestamp: When the entry was created/updated
        compressed: Whether the content is compressed
    """

    content: Any
    timestamp: datetime
    compressed: bool = False


class ContentCache:
    """Thread-safe content cache with LRU eviction, TTL, and compression support.

    The cache implements a Least Recently Used (LRU) eviction policy and supports
    Time-To-Live (TTL) for entries. It can optionally compress cached content
    using zlib compression to reduce memory usage.

    All operations are thread-safe using a reentrant lock.
    """

    def __init__(self, config: CacheConfig) -> None:
        """Initialize the content cache.

        Args:
            config: Configuration for cache behavior
        """
        self._config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache.

        Args:
            key: Cache key to look up

        Returns:
            The cached content if found and not expired, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                metrics.cache_misses.inc()
                return None

            entry = self._cache[key]
            now = datetime.now()

            # Check TTL
            if (now - entry.timestamp).total_seconds() > self._config.ttl_seconds:
                self._remove(key)
                metrics.cache_misses.inc()
                return None

            # Update access time
            self._access_order[key] = now

            # Decompress if needed
            content = entry.content
            if entry.compressed:
                try:
                    content = zlib.decompress(content)
                    content = json.loads(content.decode())
                except (zlib.error, json.JSONDecodeError):
                    metrics.cache_errors.inc()
                    self._remove(key)
                    return None

            metrics.cache_hits.inc()
            return content

    def put(self, key: str, content: Any) -> None:
        """Add or update an item in the cache.

        Args:
            key: Cache key
            content: Content to cache
        """
        with self._lock:
            # Compress if enabled
            compressed = False
            if self._config.enable_compression:
                try:
                    content_json = json.dumps(content)
                    original_size = len(content_json.encode())
                    compressed_content = zlib.compress(content_json.encode())
                    compressed_size = len(compressed_content)
                    metrics.cache_compression_ratio.set(compressed_size / original_size)
                    content = compressed_content
                    compressed = True
                except (TypeError, zlib.error, json.JSONEncodeError):
                    metrics.cache_errors.inc()

            # Evict if needed
            while len(self._cache) >= self._config.max_size:
                self._evict_lru()

            # Update cache
            now = datetime.now()
            self._cache[key] = CacheEntry(
                content=content,
                timestamp=now,
                compressed=compressed
            )
            self._access_order[key] = now
            metrics.cache_size_bytes.set(self._get_size())

    def _remove(self, key: str) -> None:
        """Remove an item from the cache.

        Args:
            key: Cache key to remove
        """
        self._cache.pop(key, None)
        self._access_order.pop(key, None)
        metrics.cache_size_bytes.set(self._get_size())

    def _evict_lru(self) -> None:
        """Evict the least recently used item from the cache."""
        if not self._access_order:
            return

        # Find oldest entry
        lru_key = min(self._access_order.items(), key=lambda x: x[1])[0]
        self._remove(lru_key)
        metrics.cache_evictions.inc()

    def _get_size(self) -> int:
        """Get the total size of cached content in bytes.

        Returns:
            Total size in bytes
        """
        return sum(
            len(str(entry.content).encode())
            for entry in self._cache.values()
        )

    def __len__(self) -> int:
        """Get the number of items in the cache.

        Returns:
            Number of cached items
        """
        return len(self._cache)
