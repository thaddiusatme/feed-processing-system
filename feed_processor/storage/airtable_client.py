"""Airtable API client for data storage and retrieval."""
import logging

import requests

logger = logging.getLogger(__name__)


class AirtableClient:
    """Client for interacting with Airtable API."""

    def __init__(self, api_key: str, base_id: str, table_name: str):
        """Initialize Airtable client.

        Args:
            api_key: Airtable API key
            base_id: Airtable base ID
            table_name: Name of the table to interact with
        """
        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name
        self.base_url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def create_record(self, record: dict) -> dict:
        """Create a new record in Airtable.

        Args:
            record: Record data to create

        Returns:
            Created record data from Airtable
        """
        response = requests.post(self.base_url, headers=self.headers, json={"fields": record})
        response.raise_for_status()
        return response.json()

    def update_record(self, record_id: str, record: dict) -> dict:
        """Update an existing record in Airtable.

        Args:
            record_id: ID of record to update
            record: Updated record data

        Returns:
            Updated record data from Airtable
        """
        response = requests.patch(
            f"{self.base_url}/{record_id}", headers=self.headers, json={"fields": record}
        )
        response.raise_for_status()
        return response.json()
