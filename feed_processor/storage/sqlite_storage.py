"""SQLite storage implementation for feed items."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import structlog
from pydantic import BaseModel

from feed_processor.storage.models import ContentItem, ContentStatus

logger = structlog.get_logger(__name__)


class SQLiteConfig(BaseModel):
    """Configuration for SQLite storage."""

    db_path: str


class SQLiteStorage:
    """SQLite storage implementation for feed items."""

    def __init__(self, config: SQLiteConfig):
        """Initialize SQLite storage.

        Args:
            config: SQLite configuration
        """
        self.db_path = Path(config.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        with self._get_connection() as conn:
            with open(Path(__file__).parent / "schema.sql") as f:
                conn.executescript(f.read())

    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def store_item(self, item: ContentItem) -> bool:
        """Store a content item in the database.

        Args:
            item: Content item to store

        Returns:
            True if item was stored successfully
        """
        try:
            record = item.to_db_record()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO feed_items (
                        title, content_type, brief, feed_id, original_url,
                        publish_date, author, processed_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["title"],
                        record["content_type"],
                        record["brief"],
                        record["feed_id"],
                        record["original_url"],
                        record["publish_date"],
                        record["author"],
                        record["processed_status"],
                    ),
                )
                return True
        except sqlite3.IntegrityError:
            # URL already exists
            logger.debug("Duplicate item", url=record["original_url"])
            return False
        except Exception as e:
            logger.error("Error storing item", error=str(e), url=record["original_url"])
            return False

    def is_duplicate(self, url: str) -> bool:
        """Check if URL already exists in database.

        Args:
            url: URL to check

        Returns:
            True if URL exists
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM feed_items WHERE original_url = ?", (url,))
            return cursor.fetchone() is not None

    def log_error(self, error_type: str, error_message: str):
        """Log an error to the database.

        Args:
            error_type: Type of error
            error_message: Error message
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO error_log (error_type, error_message) VALUES (?, ?)",
                (error_type, error_message),
            )

    def get_items_by_status(
        self, status: ContentStatus, limit: Optional[int] = None
    ) -> List[ContentItem]:
        """Get items by status.

        Args:
            status: Status to filter by
            limit: Maximum number of items to return

        Returns:
            List of content items
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM feed_items WHERE processed_status = ?"
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (status.value,))
            rows = cursor.fetchall()

            return [
                ContentItem(
                    title=row["title"],
                    contentType=row["content_type"],
                    brief=row["brief"],
                    sourceMetadata={
                        "feedId": row["feed_id"],
                        "originalUrl": row["original_url"],
                        "publishDate": datetime.fromisoformat(row["publish_date"]),
                        "author": row["author"],
                        "tags": [],  # Tags not stored in basic implementation
                    },
                )
                for row in rows
            ]
