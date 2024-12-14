"""
AI Test Fixtures
ID: FIX-001

Purpose:
Provide standardized test data for AI-assisted testing scenarios.

Categories:
1. Performance Testing
2. Security Testing
3. Edge Cases
4. Load Testing
"""

"""Test fixtures for AI-assisted feed processing tests.

This module provides mock data and fixtures for testing AI-related functionality
in the feed processing system.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from feed_processor.core.errors import FeedProcessingError


class AITestFixtures:
    """
    AI-Optimized Test Fixtures

    Provides standardized test data with specific characteristics
    for AI-assisted testing scenarios.
    """

    @staticmethod
    def get_performance_feed(size="small"):
        """
        Get feed data for performance testing

        Sizes:
        - small: 1 item
        - medium: 100 items
        - large: 1000 items

        AI Considerations:
        - Memory usage patterns
        - Processing complexity
        - Data structure impact
        """
        items = []
        if size == "small":
            count = 1
        elif size == "medium":
            count = 100
        else:
            count = 1000

        for i in range(count):
            items.append(
                {
                    "title": f"Test Item {i}",
                    "link": f"http://example.com/item{i}",
                    "description": f"Test Description {i}" * 10,
                }
            )

        return {
            "content": json.dumps(
                {
                    "channel": {
                        "title": "Performance Test Feed",
                        "link": "http://example.com/feed",
                        "description": "Performance test data",
                        "items": items,
                    }
                }
            )
        }

    @staticmethod
    def get_security_test_data():
        """
        Get test data for security testing

        Scenarios:
        1. SQL Injection attempts
        2. XSS attempts
        3. Large payloads
        4. Invalid characters

        AI Considerations:
        - Security patterns
        - Input validation
        - Resource limits
        """
        return {
            "sql_injection": {"content": "'; DROP TABLE feeds; --"},
            "xss_attempt": {"content": '<script>alert("xss")</script>'},
            "large_payload": {"content": "x" * 1000000},  # 1MB of data
            "invalid_chars": {"content": "".join(chr(i) for i in range(32))},  # Control characters
        }

    @staticmethod
    def get_edge_cases():
        """
        Get edge case test data

        Cases:
        1. Empty feed
        2. Malformed XML
        3. Unicode characters
        4. Nested content

        AI Considerations:
        - Edge case patterns
        - Error handling
        - Data validation
        """
        return {
            "empty_feed": {"content": ""},
            "malformed_xml": {"content": "<rss><channel><item></channel></rss>"},
            "unicode_content": {"content": "测试内容"},
            "nested_content": {
                "content": "<rss><channel><item><item></item></item></channel></rss>"
            },
        }

    @staticmethod
    def get_load_test_data(duration_seconds=3600):
        """
        Get load test data

        Parameters:
        - duration_seconds: Test duration

        Generates:
        - Continuous feed data
        - Varying sizes
        - Different content types

        AI Considerations:
        - Resource usage
        - Performance patterns
        - System stability
        """

        def generate_item(timestamp):
            return {
                "title": f"Load Test Item {timestamp}",
                "link": f"http://example.com/item/{timestamp}",
                "description": f"Load test description {timestamp}",
                "pubDate": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            }

        current_time = datetime.now(timezone.utc).timestamp()
        test_data = []

        for t in range(int(current_time), int(current_time + duration_seconds), 60):
            test_data.append(
                {
                    "content": json.dumps(
                        {
                            "channel": {
                                "title": "Load Test Feed",
                                "link": "http://example.com/load-test",
                                "description": "Load test data",
                                "items": [generate_item(t)],
                            }
                        }
                    )
                }
            )

        return test_data


def create_mock_feed_data(count: int = 5) -> List[Dict[str, str]]:
    """Create mock feed data for testing.

    Args:
        count: Number of mock feed items to create

    Returns:
        List of mock feed items
    """
    items = []
    for i in range(count):
        items.append(
            {
                "title": f"Mock Item {i}",
                "link": f"http://example.com/item{i}",
                "description": f"Mock Description {i}",
            }
        )
    return items
