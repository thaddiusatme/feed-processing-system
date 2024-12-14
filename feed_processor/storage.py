"""
Google Drive storage handler for feed processing system.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)


class GoogleDriveStorage:
    """Handles Google Drive storage operations."""

    def __init__(self, credentials: Credentials, root_folder_id: str):
        """
        Initialize Google Drive storage.

        Args:
            credentials: Google OAuth2 credentials
            root_folder_id: ID of the root folder for content storage
        """
        self.service = build("drive", "v3", credentials=credentials)
        self.root_folder_id = root_folder_id

    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type based on file extension."""
        extension = Path(file_path).suffix.lower()
        mime_types = {
            ".json": "application/json",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        return mime_types.get(extension, "application/octet-stream")

    def create_folder(self, folder_path: str) -> str:
        """
        Create a folder structure in Google Drive.

        Args:
            folder_path: Path relative to root folder

        Returns:
            str: ID of the created folder
        """
        current_parent = self.root_folder_id

        for folder_name in Path(folder_path).parts:
            # Check if folder exists
            query = f"name = '{folder_name}' and '{current_parent}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(q=query).execute()
            items = results.get("files", [])

            if items:
                current_parent = items[0]["id"]
            else:
                # Create new folder
                folder_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [current_parent],
                }
                folder = self.service.files().create(body=folder_metadata, fields="id").execute()
                current_parent = folder.get("id")

        return current_parent

    def write_json(self, file_path: str, data: Dict[str, Any]) -> str:
        """
        Write JSON data to a file in Google Drive.

        Args:
            file_path: Path relative to root folder
            data: Dictionary to write as JSON

        Returns:
            str: ID of the created file
        """
        # Create parent folders if needed
        parent_folder_id = self.create_folder(str(Path(file_path).parent))

        # Write data to temporary file
        temp_path = "/tmp/temp.json"
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Upload file
        file_metadata = {"name": Path(file_path).name, "parents": [parent_folder_id]}

        media = MediaFileUpload(temp_path, mimetype="application/json", resumable=True)

        file = (
            self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        )

        # Clean up temporary file
        Path(temp_path).unlink()

        return file.get("id")

    def read_json(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON data from a file in Google Drive.

        Args:
            file_path: Path relative to root folder

        Returns:
            Dict or None: Parsed JSON data if file exists
        """
        try:
            # Find file
            query = f"name = '{Path(file_path).name}' and trashed = false"
            results = self.service.files().list(q=query).execute()
            items = results.get("files", [])

            if not items:
                return None

            # Download file
            file_id = items[0]["id"]
            request = self.service.files().get_media(fileId=file_id)

            # Write to temporary file
            temp_path = "/tmp/temp.json"
            with open(temp_path, "wb") as f:
                f.write(request.execute())

            # Read JSON data
            with open(temp_path, "r") as f:
                data = json.load(f)

            # Clean up
            Path(temp_path).unlink()

            return data

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return None
