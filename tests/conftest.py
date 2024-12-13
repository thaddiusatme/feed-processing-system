import pytest
from unittest.mock import Mock
import os


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("INOREADER_TOKEN", "test_token")
    monkeypatch.setenv("WEBHOOK_URL", "http://test.com/webhook")


@pytest.fixture
def mock_queue():
    """Create a mock queue for testing."""
    queue = Mock()
    queue.empty.return_value = False
    queue.get.return_value = {"id": "1", "title": "Test"}
    return queue


@pytest.fixture
def mock_webhook_manager():
    """Create a mock webhook manager for testing."""
    manager = Mock()
    manager.send_webhook.return_value = Mock(success=True, status_code=200)
    return manager
