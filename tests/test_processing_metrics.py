import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from feed_processor.processing_metrics import ProcessingMetrics


def test_increment_processed():
    metrics = ProcessingMetrics()
    assert metrics.processed_count == 0
    metrics.increment_processed()
    assert metrics.processed_count == 1


def test_increment_errors():
    metrics = ProcessingMetrics()
    assert metrics.error_count == 0
    metrics.increment_errors()
    assert metrics.error_count == 1


def test_update_process_time():
    metrics = ProcessingMetrics()
    metrics.update_process_time(1.5)
    assert metrics.last_process_time == 1.5


def test_update_queue_length():
    metrics = ProcessingMetrics()
    metrics.update_queue_length(10)
    assert metrics.queue_length == 10


def test_success_rate_with_no_processing():
    metrics = ProcessingMetrics()
    assert metrics.success_rate == 0.0


def test_success_rate_with_processing():
    metrics = ProcessingMetrics()
    metrics.increment_processed()
    metrics.increment_processed()
    metrics.increment_errors()
    assert metrics.success_rate == pytest.approx(66.67, rel=0.01)


def test_processing_duration():
    metrics = ProcessingMetrics()

    # Mock the start time and current time
    start_time = datetime.now(timezone.utc)
    current_time = start_time + timedelta(minutes=1)

    with patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = current_time
        metrics.start_time = start_time

        # Duration should be 60 seconds
        assert metrics.processing_duration == pytest.approx(60.0, rel=0.1)


def test_reset():
    metrics = ProcessingMetrics()
    metrics.increment_processed()
    metrics.increment_errors()
    metrics.update_queue_length(5)
    metrics.update_process_time(1.5)

    metrics.reset()

    assert metrics.processed_count == 0
    assert metrics.error_count == 0
    assert metrics.queue_length == 0
    assert metrics.last_process_time == 0.0
