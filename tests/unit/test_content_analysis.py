import pytest

from feed_processor.content_analysis import ReadabilityAnalyzer


@pytest.fixture
def analyzer():
    return ReadabilityAnalyzer()


def test_calculate_flesch_kincaid_score(analyzer):
    # Test case 1: Simple text
    text = "The quick brown fox jumps over the lazy dog."
    score = analyzer.calculate_flesch_kincaid_score(text)
    assert isinstance(score, float)
    assert 0 <= score <= 100


@pytest.mark.parametrize(
    "word,expected", [("hello", 2), ("world", 1), ("beautiful", 3), ("programming", 3), ("", 0)]
)
def test_count_syllables(analyzer, word, expected):
    count = analyzer._count_syllables(word)
    assert count == expected


def test_count_sentences(analyzer):
    text = "This is one sentence. This is another! And a third?"
    count = analyzer._count_sentences(text)
    assert count == 3


def test_empty_text(analyzer):
    score = analyzer.calculate_flesch_kincaid_score("")
    assert score == 0.0


def test_complex_text(analyzer):
    text = """The intricate nature of quantum mechanics presents significant
             challenges to our understanding of fundamental particle physics.
             However, recent developments have shed new light on these phenomena."""
    score = analyzer.calculate_flesch_kincaid_score(text)
    assert isinstance(score, float)
    assert 0 <= score <= 100
