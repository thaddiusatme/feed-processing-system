"""Tests for the content caching functionality."""

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from feed_processor.cache.content_cache import CacheConfig, ContentCache
from feed_processor.metrics import CacheMetrics, get_registry


class TestContentCache(unittest.TestCase):
    """Test suite for ContentCache class."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment."""
        os.environ["PYTEST_CURRENT_TEST"] = "true"

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test environment."""
        os.environ.pop("PYTEST_CURRENT_TEST", None)

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create test metrics with test registry
        self.registry = get_registry()
        self.mock_metrics = CacheMetrics(registry=self.registry)

        self.patcher = patch("feed_processor.cache.content_cache.metrics", self.mock_metrics)
        self.patcher.start()

        self.cache_config = CacheConfig(
            max_size=1000,
            ttl_seconds=3600,
            enable_compression=True,
        )
        self.cache = ContentCache(config=self.cache_config)
        self.test_content = {
            "id": "test123",
            "title": "Test Content",
            "content": "This is test content",
            "timestamp": datetime.now().isoformat(),
        }

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.patcher.stop()
        # Clear test registry
        collectors = list(self.registry._collector_to_names.copy().keys())
        for collector in collectors:
            self.registry.unregister(collector)

    def test_cache_put_and_get(self) -> None:
        """Test basic cache put and get operations."""
        key = "test_key"
        self.cache.put(key, self.test_content)
        cached_content = self.cache.get(key)
        self.assertEqual(cached_content, self.test_content)
        self.assertEqual(
            float(self.registry.get_sample_value("cache_hits_total")),
            1.0
        )

    def test_cache_ttl(self) -> None:
        """Test that cached items expire after TTL."""
        key = "test_key"

        # Mock datetime for both cache and test
        mock_now = datetime.now()
        future_time = mock_now + timedelta(seconds=3601)

        with patch("feed_processor.cache.content_cache.datetime") as mock_datetime:
            # Set initial time for put
            mock_datetime.now.return_value = mock_now
            self.cache.put(key, self.test_content)

            # Move time forward
            mock_datetime.now.return_value = future_time
            cached_content = self.cache.get(key)

            self.assertIsNone(cached_content)
            self.assertEqual(
                float(self.registry.get_sample_value("cache_misses_total")),
                1.0
            )

    def test_cache_max_size(self) -> None:
        """Test that cache respects max size limit."""
        # Fill cache to max size
        for i in range(1100):  # More than max_size
            key = f"key_{i}"
            content = self.test_content.copy()
            content["id"] = key
            self.cache.put(key, content)

        # Verify cache size hasn't exceeded max
        self.assertLessEqual(len(self.cache), self.cache_config.max_size)
        self.assertGreater(
            float(self.registry.get_sample_value("cache_evictions_total")),
            0.0
        )

    def test_cache_compression(self) -> None:
        """Test content compression functionality."""
        key = "test_key"
        large_content = self.test_content.copy()
        large_content["content"] = "x" * 10000  # Large content

        # Put content in cache
        self.cache.put(key, large_content)

        # Get content back
        cached_content = self.cache.get(key)
        self.assertEqual(cached_content, large_content)

        # Verify compression was applied
        self.assertIsNotNone(
            self.registry.get_sample_value("cache_compression_ratio")
        )

    def test_cache_hit_miss_metrics(self) -> None:
        """Test cache hit/miss metrics."""
        key = "test_key"

        # Test miss
        self.cache.get(key)
        self.assertEqual(
            float(self.registry.get_sample_value("cache_misses_total")),
            1.0
        )

        # Test hit
        self.cache.put(key, self.test_content)
        cached_content = self.cache.get(key)
        self.assertEqual(cached_content, self.test_content)
        self.assertEqual(
            float(self.registry.get_sample_value("cache_hits_total")),
            1.0
        )

    def test_cache_eviction(self) -> None:
        """Test LRU eviction policy."""
        # Fill cache
        for i in range(1000):
            self.cache.put(f"key_{i}", self.test_content)

        # Access one item to make it most recently used
        self.cache.get("key_0")

        # Add one more item to trigger eviction
        self.cache.put("new_key", self.test_content)

        # key_0 should still be there as it was recently accessed
        self.assertIsNotNone(self.cache.get("key_0"))
        # key_1 should have been evicted
        self.assertIsNone(self.cache.get("key_1"))
        self.assertGreater(
            float(self.registry.get_sample_value("cache_evictions_total")),
            0.0
        )


if __name__ == "__main__":
    unittest.main()
