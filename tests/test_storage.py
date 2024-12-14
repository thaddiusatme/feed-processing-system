"""Tests for Google Drive storage."""
import json
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from feed_processor.storage import GoogleDriveStorage


@pytest.fixture
def mock_credentials():
    return Mock(spec=Credentials)


@pytest.fixture
def mock_service():
    service = Mock()

    # Mock files().list().execute()
    files_list = Mock()
    files_list.execute = Mock(return_value={"files": []})
    files = Mock()
    files.list = Mock(return_value=files_list)
    service.files = Mock(return_value=files)

    return service


@pytest.fixture
def storage(mock_credentials, mock_service):
    with patch("feed_processor.storage.build", return_value=mock_service):
        return GoogleDriveStorage(mock_credentials, "root_folder_id")


def test_get_mime_type(storage):
    """Test MIME type detection."""
    assert storage._get_mime_type("test.json") == "application/json"
    assert storage._get_mime_type("test.txt") == "text/plain"
    assert storage._get_mime_type("test.md") == "text/markdown"
    assert storage._get_mime_type("test.unknown") == "application/octet-stream"


def test_create_folder_new(storage, mock_service):
    """Test creating a new folder."""
    # Mock empty search results
    files_list = Mock()
    files_list.execute = Mock(return_value={"files": []})

    # Mock folder creation
    create = Mock()
    create.execute = Mock(return_value={"id": "new_folder_id"})

    files = Mock()
    files.list = Mock(return_value=files_list)
    files.create = Mock(return_value=create)
    mock_service.files = Mock(return_value=files)

    folder_id = storage.create_folder("test_folder")
    assert folder_id == "new_folder_id"

    # Verify create call
    create_call = mock_service.files().create.call_args
    assert create_call.kwargs["body"]["name"] == "test_folder"
    assert create_call.kwargs["body"]["mimeType"] == "application/vnd.google-apps.folder"
    assert create_call.kwargs["body"]["parents"] == ["root_folder_id"]


def test_create_folder_existing(storage, mock_service):
    """Test creating a folder that already exists."""
    # Mock existing folder
    files_list = Mock()
    files_list.execute = Mock(return_value={"files": [{"id": "existing_folder_id"}]})

    files = Mock()
    files.list = Mock(return_value=files_list)
    mock_service.files = Mock(return_value=files)

    folder_id = storage.create_folder("test_folder")
    assert folder_id == "existing_folder_id"

    # Verify no create call was made
    assert not mock_service.files().create.called


def test_write_json(storage, mock_service):
    """Test writing JSON data."""
    test_data = {"test": "data"}

    # Mock folder creation
    create_folder = Mock()
    create_folder.execute = Mock(return_value={"id": "folder_id"})

    # Mock file creation
    create_file = Mock()
    create_file.execute = Mock(return_value={"id": "file_id"})

    files = Mock()
    files.create = Mock(side_effect=[create_folder, create_file])
    mock_service.files = Mock(return_value=files)

    file_id = storage.write_json("test/file.json", test_data)
    assert file_id == "file_id"

    # Verify file creation call
    create_call = mock_service.files().create.call_args_list[-1]
    assert create_call.kwargs["body"]["name"] == "file.json"
    assert create_call.kwargs["body"]["parents"] == ["folder_id"]
    assert isinstance(create_call.kwargs["media_body"], MediaFileUpload)


def test_read_json(storage, mock_service):
    """Test reading JSON data."""
    test_data = {"test": "data"}

    # Mock file search
    files_list = Mock()
    files_list.execute = Mock(return_value={"files": [{"id": "file_id"}]})

    # Mock file download
    get_media = Mock()
    get_media.execute = Mock(return_value=json.dumps(test_data).encode())

    files = Mock()
    files.list = Mock(return_value=files_list)
    files.get_media = Mock(return_value=get_media)
    mock_service.files = Mock(return_value=files)

    result = storage.read_json("test/file.json")
    assert result == test_data

    # Verify get_media call
    assert mock_service.files().get_media.called
    get_media_call = mock_service.files().get_media.call_args
    assert get_media_call.kwargs["fileId"] == "file_id"


def test_read_json_not_found(storage, mock_service):
    """Test reading non-existent JSON file."""
    # Mock empty search results
    files_list = Mock()
    files_list.execute = Mock(return_value={"files": []})

    files = Mock()
    files.list = Mock(return_value=files_list)
    mock_service.files = Mock(return_value=files)

    result = storage.read_json("test/nonexistent.json")
    assert result is None
