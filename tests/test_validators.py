import unittest
from datetime import datetime

from feed_processor.validators import FeedValidationResult, FeedValidator


class TestFeedValidator(unittest.TestCase):
    def setUp(self):
        self.rss_feed = """<?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0">
        <channel>
            <title>Sample RSS Feed</title>
            <link>http://example.com/feed</link>
            <description>A sample RSS feed for testing</description>
            <pubDate>Mon, 13 Dec 2024 03:01:14 -0800</pubDate>
            <item>
                <title>First Post</title>
                <link>http://example.com/first-post</link>
                <description>This is the first post</description>
                <pubDate>Mon, 13 Dec 2024 03:00:00 -0800</pubDate>
            </item>
        </channel>
        </rss>"""

        self.atom_feed = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Sample Atom Feed</title>
            <link href="http://example.com/feed"/>
            <id>urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6</id>
            <updated>2024-12-13T03:01:14-08:00</updated>
            <entry>
                <title>First Entry</title>
                <link href="http://example.com/first-entry"/>
                <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
                <updated>2024-12-13T03:00:00-08:00</updated>
                <summary>This is the first entry</summary>
            </entry>
        </feed>"""

        self.json_feed = """{
            "version": "https://jsonfeed.org/version/1.1",
            "title": "Sample JSON Feed",
            "home_page_url": "http://example.com/",
            "feed_url": "http://example.com/feed.json",
            "items": [
                {
                    "id": "1",
                    "title": "First Item",
                    "content_text": "This is the first item",
                    "url": "http://example.com/first-item",
                    "date_published": "2024-12-13T03:00:00-08:00"
                }
            ]
        }"""

        self.invalid_feed = "This is not a valid feed"

    def test_validate_rss_feed(self):
        result = FeedValidator.validate_feed(self.rss_feed)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.feed_type, "rss")
        self.assertIsNotNone(result.parsed_feed)
        self.assertEqual(result.parsed_feed["title"], "Sample RSS Feed")

    def test_validate_atom_feed(self):
        result = FeedValidator.validate_feed(self.atom_feed)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.feed_type, "atom")
        self.assertIsNotNone(result.parsed_feed)
        self.assertEqual(result.parsed_feed["title"], "Sample Atom Feed")

    def test_validate_json_feed(self):
        result = FeedValidator.validate_feed(self.json_feed)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.feed_type, "json")
        self.assertIsNotNone(result.parsed_feed)
        self.assertEqual(result.parsed_feed["title"], "Sample JSON Feed")

    def test_validate_invalid_feed(self):
        result = FeedValidator.validate_feed(self.invalid_feed)
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.feed_type)
        self.assertIsNotNone(result.error_message)

    def test_validate_missing_required_fields(self):
        invalid_rss = """<?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0">
        <channel>
            <title>Sample RSS Feed</title>
            <description>Missing link field</description>
        </channel>
        </rss>"""

        result = FeedValidator.validate_feed(invalid_rss)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.feed_type, "rss")
        self.assertIn("Missing required fields", result.error_message)

    def test_normalize_dates(self):
        result = FeedValidator.validate_feed(self.rss_feed)
        self.assertIsInstance(result.parsed_feed["updated"], datetime)

        result = FeedValidator.validate_feed(self.atom_feed)
        self.assertIsInstance(result.parsed_feed["updated"], datetime)


if __name__ == "__main__":
    unittest.main()
