"""
Airtable client for handling data storage and retrieval.
"""
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field, validator

from feed_processor.config import settings
from feed_processor.errors import StorageError
from feed_processor.metrics.prometheus import metrics

logger = logging.getLogger(__name__)


class AirtableConfig(BaseModel):
    """Configuration for Airtable client."""

    api_key: str = Field(..., description="Airtable API key")
    base_id: str = Field(..., description="Airtable base ID (starts with 'app')")
    table_id: str = Field(..., description="Airtable table ID (starts with 'tbl')")
    rate_limit_per_sec: float = Field(
        default=0.2, description="Rate limit in seconds between requests"
    )
    batch_size: int = Field(default=10, description="Number of records to process in each batch")

    @validator("base_id")
    def validate_base_id(cls, v):
        if not re.match(r"^app[a-zA-Z0-9]+$", v):
            raise ValueError("Base ID must start with 'app'")
        return v

    @validator("table_id")
    def validate_table_id(cls, v):
        if not re.match(r"^tbl[a-zA-Z0-9]+$", v):
            raise ValueError("Table ID must start with 'tbl'")
        return v


class AirtableClient:
    """Client for interacting with Airtable API."""

    def __init__(self, config: AirtableConfig):
        self.config = config
        self.base_url = f"https://api.airtable.com/v0/{config.base_id}"
        self.api_url = f"{self.base_url}/{config.table_id}"
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        self._last_request_time = 0

        # Register metrics
        metrics.register_counter(
            "airtable_requests_total",
            "Total number of requests made to Airtable API",
            ["operation", "status"],
        )
        metrics.register_histogram(
            "airtable_request_duration_seconds", "Duration of Airtable API requests", ["operation"]
        )

    def _rate_limit(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.config.rate_limit_per_sec:
            sleep_time = self.config.rate_limit_per_sec - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    async def create_records(self, records: List[Dict]) -> List[str]:
        """Create multiple records in Airtable.

        Args:
            records: List of record dictionaries to create

        Returns:
            List of created record IDs

        Raises:
            StorageError: If the API request fails
        """
        if not records:
            return []

        record_ids = []
        for i in range(0, len(records), self.config.batch_size):
            batch = records[i : i + self.config.batch_size]

            try:
                self._rate_limit()
                start_time = time.time()

                response = requests.post(
                    self.api_url, headers=self.headers, json={"records": batch}
                )

                metrics.observe_histogram(
                    "airtable_request_duration_seconds",
                    time.time() - start_time,
                    {"operation": "create"},
                )

                if response.status_code != 200:
                    metrics.increment_counter(
                        "airtable_requests_total", {"operation": "create", "status": "error"}
                    )
                    raise StorageError(f"Failed to create records: {response.text}")

                metrics.increment_counter(
                    "airtable_requests_total", {"operation": "create", "status": "success"}
                )

                result = response.json()
                record_ids.extend([r["id"] for r in result["records"]])

            except requests.RequestException as e:
                metrics.increment_counter(
                    "airtable_requests_total", {"operation": "create", "status": "error"}
                )
                raise StorageError(f"Request failed: {str(e)}")

        return record_ids

    async def get_record(self, record_id: str) -> Optional[Dict]:
        """Retrieve a single record from Airtable.

        Args:
            record_id: ID of the record to retrieve

        Returns:
            Record dictionary if found, None if not found

        Raises:
            StorageError: If the API request fails
        """
        try:
            self._rate_limit()
            start_time = time.time()

            response = requests.get(f"{self.api_url}/{record_id}", headers=self.headers)

            metrics.observe_histogram(
                "airtable_request_duration_seconds", time.time() - start_time, {"operation": "get"}
            )

            if response.status_code == 404:
                metrics.increment_counter(
                    "airtable_requests_total", {"operation": "get", "status": "not_found"}
                )
                return None

            if response.status_code != 200:
                metrics.increment_counter(
                    "airtable_requests_total", {"operation": "get", "status": "error"}
                )
                raise StorageError(f"Failed to get record: {response.text}")

            metrics.increment_counter(
                "airtable_requests_total", {"operation": "get", "status": "success"}
            )

            return response.json()

        except requests.RequestException as e:
            metrics.increment_counter(
                "airtable_requests_total", {"operation": "get", "status": "error"}
            )
            raise StorageError(f"Request failed: {str(e)}")
