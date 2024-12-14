"""SQLite database module for storing feed items."""

import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class Database:
    """SQLite database for storing feed items."""

    def __init__(self, db_path: str = "feeds.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create feeds table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feeds (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    link TEXT,
                    pub_date TIMESTAMP,
                    author TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create tags table for many-to-many relationship
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """
            )

            # Create feed_tags table for many-to-many relationship
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feed_tags (
                    feed_id TEXT,
                    tag_id INTEGER,
                    FOREIGN KEY (feed_id) REFERENCES feeds(id),
                    FOREIGN KEY (tag_id) REFERENCES tags(id),
                    PRIMARY KEY (feed_id, tag_id)
                )
            """
            )

            conn.commit()

    def add_feed(self, feed_data: Dict) -> bool:
        """Add a feed item to the database.

        Args:
            feed_data: Feed data dictionary containing id, title, description, etc.

        Returns:
            bool: True if feed was added successfully
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert feed
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO feeds (id, title, description, link, pub_date, author)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        feed_data["id"],
                        feed_data["feed"]["title"],
                        feed_data["feed"]["description"],
                        str(feed_data["feed"]["link"]),  # Convert HttpUrl to string
                        feed_data["feed"]["pubDate"],
                        feed_data["feed"]["author"],
                    ),
                )

                # Insert tags
                for tag in feed_data["feed"]["tags"]:
                    # Insert tag if it doesn't exist
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO tags (name) VALUES (?)
                    """,
                        (tag,),
                    )

                    # Get tag id
                    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                    tag_id = cursor.fetchone()[0]

                    # Link tag to feed
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO feed_tags (feed_id, tag_id)
                        VALUES (?, ?)
                    """,
                        (feed_data["id"], tag_id),
                    )

                conn.commit()
                return True

        except Exception as e:
            logger.error("Error adding feed to database", error=str(e))
            return False

    def get_feeds(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """Get feed items from the database.

        Args:
            limit: Optional limit on number of items to return
            offset: Number of items to skip

        Returns:
            List[Dict]: List of feed items
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Build query
                query = """
                    SELECT
                        f.*,
                        GROUP_CONCAT(t.name) as tags
                    FROM feeds f
                    LEFT JOIN feed_tags ft ON f.id = ft.feed_id
                    LEFT JOIN tags t ON ft.tag_id = t.id
                    GROUP BY f.id
                    ORDER BY f.pub_date DESC
                """

                if limit is not None:
                    query += f" LIMIT {limit} OFFSET {offset}"

                cursor.execute(query)
                rows = cursor.fetchall()

                # Convert rows to dictionaries
                feeds = []
                for row in rows:
                    feed = dict(row)
                    feed["tags"] = feed["tags"].split(",") if feed["tags"] else []
                    feeds.append(feed)

                return feeds

        except Exception as e:
            logger.error("Error getting feeds from database", error=str(e))
            return []

    def get_feed_by_id(self, feed_id: str) -> Optional[Dict]:
        """Get a specific feed item by ID.

        Args:
            feed_id: ID of the feed to get

        Returns:
            Optional[Dict]: Feed item if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        f.*,
                        GROUP_CONCAT(t.name) as tags
                    FROM feeds f
                    LEFT JOIN feed_tags ft ON f.id = ft.feed_id
                    LEFT JOIN tags t ON ft.tag_id = t.id
                    WHERE f.id = ?
                    GROUP BY f.id
                """,
                    (feed_id,),
                )

                row = cursor.fetchone()
                if row:
                    feed = dict(row)
                    feed["tags"] = feed["tags"].split(",") if feed["tags"] else []
                    return feed
                return None

        except Exception as e:
            logger.error("Error getting feed from database", error=str(e))
            return None
