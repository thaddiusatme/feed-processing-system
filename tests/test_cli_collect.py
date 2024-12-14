"""Tests for feed collector CLI."""
import os
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from feed_processor.cli.collect import collect


@patch("feed_processor.cli.collect.FeedCollector")
def test_collect_command(mock_collector):
    """Test collect command with default options."""
    # Mock the collector's start method
    instance = mock_collector.return_value
    instance.start = AsyncMock()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(collect, ["--api-token", "test_token"])

        assert result.exit_code == 0
        mock_collector.assert_called_once()
        instance.start.assert_called_once()


@patch("feed_processor.cli.collect.FeedCollector")
def test_collect_command_with_custom_options(mock_collector):
    """Test collect command with custom options."""
    instance = mock_collector.return_value
    instance.start = AsyncMock()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            collect,
            ["--api-token", "test_token", "--db-path", "./custom/path.db", "--interval", "30.0"],
        )

        assert result.exit_code == 0

        # Verify collector was created with custom options
        config = mock_collector.call_args[0][0]
        assert config.storage.db_path == "./custom/path.db"
        assert config.collection_interval == 30.0


@patch("feed_processor.cli.collect.FeedCollector")
def test_collect_command_creates_db_directory(mock_collector):
    """Test collect command creates database directory."""
    instance = mock_collector.return_value
    instance.start = AsyncMock()

    runner = CliRunner()
    with runner.isolated_filesystem():
        db_path = "data/feeds.db"
        result = runner.invoke(collect, ["--api-token", "test_token", "--db-path", db_path])

        assert result.exit_code == 0
        assert os.path.exists("data")


@patch("feed_processor.cli.collect.FeedCollector")
def test_collect_command_keyboard_interrupt(mock_collector):
    """Test collect command handles keyboard interrupt."""
    instance = mock_collector.return_value
    instance.start = AsyncMock(side_effect=KeyboardInterrupt)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(collect, ["--api-token", "test_token"])

        assert result.exit_code == 0
        instance.stop.assert_called_once()
