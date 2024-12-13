"""Schema migration utilities for the feed processing system."""
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel


def migrate_source_content(old_data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate old source content format to new schema."""
    return {
        "content_id": old_data.get("id"),
        "source": old_data.get("source", "unknown"),
        "content": {
            "title": old_data.get("title", ""),
            "body": old_data.get("content", ""),
            "summary": old_data.get("summary", ""),
            "url": old_data.get("url", ""),
        },
        "metadata": {
            "author": old_data.get("author", ""),
            "published_date": old_data.get("pub_date", datetime.now().isoformat()),
            "language": old_data.get("lang", "en"),
            "categories": old_data.get("categories", []),
            "tags": old_data.get("tags", []),
        },
        "metrics": {
            "word_count": len(old_data.get("content", "").split()),
            "read_time": len(old_data.get("content", "").split()) // 200,
            "engagement_score": old_data.get("engagement", 0),
        },
        "processing": {
            "status": "migrated",
            "last_updated": datetime.now().isoformat(),
            "version": "1.0",
        },
    }


def migrate_generated_content(old_data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate old generated content format to new schema."""
    return {
        "content_id": old_data.get("id"),
        "source_id": old_data.get("source_id"),
        "content": {
            "title": old_data.get("gen_title", ""),
            "body": old_data.get("gen_content", ""),
            "summary": old_data.get("gen_summary", ""),
        },
        "metadata": {
            "generated_date": datetime.now().isoformat(),
            "model_version": old_data.get("model_version", "1.0"),
            "prompt_id": old_data.get("prompt_id"),
        },
        "quality_metrics": {
            "coherence_score": old_data.get("quality", {}).get("coherence", 0),
            "relevance_score": old_data.get("quality", {}).get("relevance", 0),
            "creativity_score": old_data.get("quality", {}).get("creativity", 0),
        },
        "status": {
            "review_status": old_data.get("status", "pending"),
            "publish_status": old_data.get("published", False),
            "last_updated": datetime.now().isoformat(),
        },
    }


def migrate_batch(items: List[Dict[str, Any]], content_type: str) -> List[Dict[str, Any]]:
    """Migrate a batch of items based on content type."""
    if content_type == "source":
        return [migrate_source_content(item) for item in items]
    elif content_type == "generated":
        return [migrate_generated_content(item) for item in items]
    else:
        raise ValueError(f"Unknown content type: {content_type}")


def validate_migration(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
    """Validate that the migration preserved all necessary data."""
    # Implement validation logic based on your requirements
    required_fields = ["content_id", "content", "metadata"]
    return all(field in new_data for field in required_fields)


def rollback_migration(backup_data: Dict[str, Any]) -> Dict[str, Any]:
    """Rollback to previous schema version if needed."""
    # Implement rollback logic
    return backup_data
