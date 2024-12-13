import unittest

from feed_processor.validator import ReadabilityAnalyzer


class TestReadabilityMetrics(unittest.TestCase):
    def setUp(self):
        self.analyzer = ReadabilityAnalyzer()

    def test_clean_text_basic(self):
        text = "This is a simple sentence."
        cleaned_text = self.analyzer._clean_text(text)
        self.assertEqual(cleaned_text, "This is a simple sentence.")

    def test_clean_text_with_punctuation(self):
        text = "Hello, world! How's it going?"
        cleaned_text = self.analyzer._clean_text(text)
        self.assertEqual(cleaned_text, "Hello world Hows it going")

    def test_clean_text_with_numbers(self):
        text = "The year is 2024."
        cleaned_text = self.analyzer._clean_text(text)
        self.assertEqual(cleaned_text, "The year is ")

    def test_clean_text_empty(self):
        text = ""
        cleaned_text = self.analyzer._clean_text(text)
        self.assertEqual(cleaned_text, "")


if __name__ == "__main__":
    unittest.main()
