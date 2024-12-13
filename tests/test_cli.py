import asyncio
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from click.testing import CliRunner
from prometheus_client import CollectorRegistry

from feed_processor.cli import cli, load_config
from feed_processor.metrics import (
    PROCESSING_LATENCY,
    PROCESSING_RATE,
    QUEUE_OVERFLOWS,
    QUEUE_SIZE,
    RATE_LIMIT_DELAY,
    WEBHOOK_PAYLOAD_SIZE,
    WEBHOOK_RETRIES,
    start_metrics_server,
)
from feed_processor.processor import FeedProcessor


class AsyncCliRunner(CliRunner):
    """Async Click test runner."""

    def invoke(self, *args, **kwargs):
        """Run command synchronously."""
        return super().invoke(*args, **kwargs)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = AsyncCliRunner()
        self.sample_config = {
            "max_queue_size": 500,
            "webhook_endpoint": "https://example.com/webhook",
            "webhook_auth_token": "test-token",
            "webhook_batch_size": 5,
        }

        self.sample_feed = """
        <?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>http://example.com/feed</link>
            <description>Test Description</description>
            <item>
                <title>Test Item</title>
                <link>http://example.com/item1</link>
                <description>Test Item Description</description>
            </item>
        </channel>
        </rss>
        """

        # Mock metrics
        self._mock_metrics()

    def _mock_metrics(self):
        """Mock all metrics to avoid port conflicts."""
        self.mock_registry = CollectorRegistry()

        # Mock all metric values
        for metric in [
            PROCESSING_RATE,
            QUEUE_SIZE,
            PROCESSING_LATENCY,
            WEBHOOK_RETRIES,
            WEBHOOK_PAYLOAD_SIZE,
            RATE_LIMIT_DELAY,
            QUEUE_OVERFLOWS,
        ]:
            metric._value = MagicMock(get=lambda: 0.0)
            metric._sum = MagicMock(get=lambda: 0.0)
            metric._count = MagicMock(get=lambda: 1.0)

    @patch("time.sleep", return_value=None)
    def test_load_config(self, mock_sleep):
        """Test loading configuration."""
        with self.runner.isolated_filesystem():
            # Write test config
            config_path = Path("test_config.json")
            with open(config_path, "w") as f:
                json.dump(self.sample_config, f)

            # Test loading config
            config = load_config(config_path)
            self.assertEqual(config["webhook_endpoint"], "https://example.com/webhook")
            self.assertEqual(config["webhook_batch_size"], 5)

            # Test loading non-existent config
            config = load_config(Path("nonexistent.json"))
            self.assertEqual(config["webhook_batch_size"], 10)  # default value

    @patch("feed_processor.cli.FeedProcessor")
    @patch("feed_processor.metrics.start_metrics_server")
    @patch("time.sleep")
    def test_start_command(self, mock_sleep, mock_metrics, MockProcessor):
        """Test the start command."""
        # Setup mock processor
        mock_processor = Mock()
        mock_processor.start = Mock()
        mock_processor.stop = Mock()
        mock_processor._running = True
        mock_processor._stop_event = Mock()
        MockProcessor.return_value = mock_processor

        # Simulate Ctrl+C after first sleep
        mock_sleep.side_effect = KeyboardInterrupt()

        # Run command
        result = self.runner.invoke(cli, ["start"])

        # Verify results
        self.assertEqual(result.exit_code, 0)
        mock_processor.start.assert_called_once()
        mock_processor.stop.assert_called_once()

    @patch("feed_processor.cli.FeedProcessor")
    @patch("time.sleep", return_value=None)
    def test_process_command(self, mock_sleep, MockProcessor):
        """Test the process command."""
        # Setup mock processor
        mock_processor = Mock()
        mock_processor.start = Mock()
        mock_processor.stop = Mock()
        mock_processor.add_feed = Mock(return_value=True)
        mock_processor._running = True
        mock_processor._stop_event = Mock()
        MockProcessor.return_value = mock_processor

        with self.runner.isolated_filesystem():
            # Create test feed file
            feed_path = Path("test_feed.xml")
            with open(feed_path, "w") as f:
                f.write(self.sample_feed)

            # Run command
            result = self.runner.invoke(cli, ["process", str(feed_path)])

            # Verify results
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Successfully added feed", result.output)
            mock_processor.start.assert_called_once()
            mock_processor.stop.assert_called_once()
            mock_processor.add_feed.assert_called_once()

    @patch("feed_processor.metrics.start_metrics_server")
    @patch("time.sleep", return_value=None)
    def test_metrics_command(self, mock_sleep, mock_metrics):
        """Test the metrics command."""
        result = self.runner.invoke(cli, ["metrics"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Current Metrics:", result.output)

    @patch("feed_processor.webhook.WebhookConfig")
    @patch("time.sleep", return_value=None)
    def test_configure_command(self, mock_sleep, MockWebhookConfig):
        """Test the configure command."""
        # Setup mock webhook config
        mock_config = Mock()
        mock_config.endpoint = "https://example.com/webhook"
        mock_config.auth_token = "test-token"
        mock_config.batch_size = 5
        MockWebhookConfig.return_value = mock_config

        with self.runner.isolated_filesystem():
            output_path = Path("config.json")
            result = self.runner.invoke(
                cli,
                [
                    "configure",
                    "--endpoint",
                    "https://example.com/webhook",
                    "--token",
                    "test-token",
                    "--batch-size",
                    "5",
                    "--output",
                    str(output_path),
                ],
            )

            # Verify results
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(output_path.exists())

            with open(output_path) as f:
                config = json.load(f)
                self.assertEqual(config["webhook_endpoint"], "https://example.com/webhook")
                self.assertEqual(config["webhook_batch_size"], 5)

    def test_configure_invalid_webhook(self):
        """Test configure command with invalid webhook URL."""
        result = self.runner.invoke(
            cli, ["configure", "--endpoint", "not-a-url", "--token", "test-token"]
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Invalid configuration", result.output)

    def test_validate_feed(self):
        """Test the new validate feed command"""
        with self.runner.isolated_filesystem():
            valid_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>"""

            with open("valid_feed.xml", "w", encoding="utf-8") as f:
                f.write(valid_feed)

            result = self.runner.invoke(cli, ["validate", "valid_feed.xml"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Feed is valid", result.output)

    def test_validate_feed_additional_checks(self):
        """Test additional feed validation checks"""
        # Test feed with empty items
        with self.runner.isolated_filesystem():
            empty_items_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
            </channel>
            </rss>"""

            with open("empty_feed.xml", "w", encoding="utf-8") as f:
                f.write(empty_items_feed)

            result = self.runner.invoke(cli, ["validate", "empty_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("No feed items found", result.output)

        # Test feed with invalid publication date
        with self.runner.isolated_filesystem():
            invalid_date_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <pubDate>Invalid Date</pubDate>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                    <pubDate>Not a valid date</pubDate>
                </item>
            </channel>
            </rss>"""

            with open("invalid_date_feed.xml", "w", encoding="utf-8") as f:
                f.write(invalid_date_feed)

            result = self.runner.invoke(cli, ["validate", "invalid_date_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid publication date", result.output)

        # Test feed with invalid URLs
        with self.runner.isolated_filesystem():
            invalid_url_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>not_a_valid_url</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>also_not_valid</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>"""

            with open("invalid_url_feed.xml", "w", encoding="utf-8") as f:
                f.write(invalid_url_feed)

            result = self.runner.invoke(cli, ["validate", "invalid_url_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid URL format", result.output)

    def test_validate_feed_strict_mode(self):
        """Test feed validation with strict mode enabled"""
        # Test feed with long content
        with self.runner.isolated_filesystem():
            very_long_title = "A" * 201  # Exceeds 200 char limit
            long_content_feed = f"""<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>{very_long_title}</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>"""

            with open("long_content_feed.xml", "w", encoding="utf-8") as f:
                f.write(long_content_feed)

            # Should pass in normal mode
            result = self.runner.invoke(cli, ["validate", "long_content_feed.xml"])
            self.assertEqual(result.exit_code, 0)

            # Should fail in strict mode
            result = self.runner.invoke(cli, ["validate", "--strict", "long_content_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Content length exceeds maximum", result.output)

        # Test feed with non-UTF8 encoding
        with self.runner.isolated_filesystem():
            non_utf8_feed = """<?xml version="1.0" encoding="ISO-8859-1" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description with special char: ñ</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>""".encode(
                "iso-8859-1"
            )

            with open("non_utf8_feed.xml", "wb") as f:
                f.write(non_utf8_feed)

            # Should pass in normal mode
            result = self.runner.invoke(cli, ["validate", "non_utf8_feed.xml"])
            self.assertEqual(result.exit_code, 0)

            # Should fail in strict mode
            result = self.runner.invoke(cli, ["validate", "--strict", "non_utf8_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Non-UTF8 encoding detected", result.output)

        # Test feed with missing optional elements
        with self.runner.isolated_filesystem():
            minimal_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                </item>
            </channel>
            </rss>"""

            with open("minimal_feed.xml", "w", encoding="utf-8") as f:
                f.write(minimal_feed)

            # Should pass in normal mode
            result = self.runner.invoke(cli, ["validate", "minimal_feed.xml"])
            self.assertEqual(result.exit_code, 0)

            # Should fail in strict mode due to missing description
            result = self.runner.invoke(cli, ["validate", "--strict", "minimal_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Missing recommended elements", result.output)

    def test_validate_feed_enhanced(self):
        """Test enhanced feed validation features."""
        with self.runner.isolated_filesystem():
            # Test with invalid GUID
            feed_with_long_guid = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                    <guid>{}</guid>
                </item>
            </channel>
            </rss>""".format(
                "x" * 513
            )  # GUID longer than 512 chars

            with open("invalid_guid_feed.xml", "w", encoding="utf-8") as f:
                f.write(feed_with_long_guid)

            result = self.runner.invoke(cli, ["validate", "invalid_guid_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("GUID exceeds maximum length", result.output)

            # Test with invalid image URL
            feed_with_invalid_image = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                    <image>not_a_url</image>
                </item>
            </channel>
            </rss>"""

            with open("invalid_image_feed.xml", "w", encoding="utf-8") as f:
                f.write(feed_with_invalid_image)

            result = self.runner.invoke(cli, ["validate", "invalid_image_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid image URL format", result.output)

            # Test with invalid categories
            feed_with_invalid_categories = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                    <category></category>
                    <category>{}</category>
                </item>
            </channel>
            </rss>""".format(
                "x" * 201
            )  # Category longer than 200 chars

            with open("invalid_categories_feed.xml", "w", encoding="utf-8") as f:
                f.write(feed_with_invalid_categories)

            result = self.runner.invoke(cli, ["validate", "invalid_categories_feed.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Category exceeds maximum length", result.output)
            self.assertIn("Empty category found", result.output)

    def test_validate_feed_json_output(self):
        """Test JSON output format for feed validation."""
        with self.runner.isolated_filesystem():
            valid_feed = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>"""

            with open("valid_feed.xml", "w", encoding="utf-8") as f:
                f.write(valid_feed)

            result = self.runner.invoke(cli, ["validate", "--format", "json", "valid_feed.xml"])
            self.assertEqual(result.exit_code, 0)

            # Verify JSON output
            import json

            try:
                output = json.loads(result.output)
                self.assertTrue(isinstance(output, dict))
                self.assertTrue(output["is_valid"])
                self.assertTrue("stats" in output)
                self.assertTrue("validation_time" in output)
            except json.JSONDecodeError:
                self.fail("Output is not valid JSON")

    def test_validate_feed_caching(self):
        """Test feed validation caching."""
        with self.runner.isolated_filesystem():
            # Create a valid feed file
            feed_content = """<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <link>http://example.com/feed</link>
                <description>Test Description</description>
                <item>
                    <title>Test Item</title>
                    <link>http://example.com/item1</link>
                    <description>Test Description</description>
                </item>
            </channel>
            </rss>"""

            with open("test_feed.xml", "w", encoding="utf-8") as f:
                f.write(feed_content)

            # First validation (should be slower)
            start_time = time.time()
            result1 = self.runner.invoke(cli, ["validate", "test_feed.xml", "--cache"])
            time1 = time.time() - start_time

            # Second validation (should be faster due to caching)
            start_time = time.time()
            result2 = self.runner.invoke(cli, ["validate", "test_feed.xml", "--cache"])
            time2 = time.time() - start_time

            # Third validation with no cache (should be slower)
            start_time = time.time()
            result3 = self.runner.invoke(cli, ["validate", "test_feed.xml", "--no-cache"])
            time3 = time.time() - start_time

            # Assertions
            self.assertEqual(result1.exit_code, 0)
            self.assertEqual(result2.exit_code, 0)
            self.assertEqual(result3.exit_code, 0)

            # Time comparisons
            self.assertGreater(time1, time2)  # Cached should be faster
            self.assertGreater(time3, time2)  # Non-cached should be slower

    @patch("time.sleep", return_value=None)
    def test_validate_command_error_types(self, mock_sleep):
        """Test different validation error types and exit codes."""
        with self.runner.isolated_filesystem():
            # Test critical error (empty file)
            with open("empty.xml", "w") as f:
                pass

            result = self.runner.invoke(cli, ["validate", "empty.xml"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Critical Error:", result.output)

            # Test validation error (missing required fields)
            invalid_feed = """<?xml version="1.0"?>
            <rss version="2.0">
            <channel>
            </channel>
            </rss>"""
            with open("invalid.xml", "w") as f:
                f.write(invalid_feed)

            result = self.runner.invoke(cli, ["validate", "invalid.xml"])
            self.assertEqual(result.exit_code, 2)
            self.assertIn("Validation Error:", result.output)

            # Test format error (invalid date)
            malformed_feed = """<?xml version="1.0"?>
            <rss version="2.0">
            <channel>
                <title>Test</title>
                <link>http://example.com</link>
                <description>Test feed</description>
                <pubDate>invalid-date</pubDate>
            </channel>
            </rss>"""
            with open("malformed.xml", "w") as f:
                f.write(malformed_feed)

            result = self.runner.invoke(cli, ["validate", "malformed.xml"])
            self.assertEqual(result.exit_code, 3)
            self.assertIn("Format Error:", result.output)

            # Test JSON output format
            result = self.runner.invoke(cli, ["validate", "--format=json", "invalid.xml"])
            self.assertEqual(result.exit_code, 2)
            output = json.loads(result.output)
            self.assertEqual(output["error_type"], "validation")
            self.assertFalse(output["is_valid"])
            self.assertTrue(len(output["errors"]) > 0)


if __name__ == "__main__":
    unittest.main()
