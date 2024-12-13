"""Schema definitions and validation for feed processing system."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


class SourceContentMetadata(BaseModel):
    """Metadata for source content."""

    source: str = Field(..., description="Content source identifier")
    author: Optional[str] = Field(None, description="Content author")
    publish_date: Optional[datetime] = Field(None, description="Original publication date")
    fetch_date: datetime = Field(
        default_factory=datetime.utcnow, description="When content was fetched"
    )
    language: Optional[str] = Field(None, description="Content language (ISO 639-1)")


class ContentMetrics(BaseModel):
    """Metrics for content evaluation."""

    views: Optional[int] = Field(0, description="Number of views")
    shares: Optional[int] = Field(0, description="Number of shares")
    comments: Optional[int] = Field(0, description="Number of comments")
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="Content quality score")
    readability_score: Optional[float] = Field(
        None, ge=0, le=100, description="Content readability score"
    )


class ContentAnalysis(BaseModel):
    """Content analysis results."""

    topics: List[str] = Field(default_factory=list, description="Detected topics")
    key_phrases: List[str] = Field(default_factory=list, description="Extracted key phrases")
    sentiment: Optional[float] = Field(None, ge=-1, le=1, description="Content sentiment score")
    content_type: str = Field(..., description="Content type classification")
    is_training_candidate: bool = Field(False, description="Whether suitable for training")


class ProcessingStatus(BaseModel):
    """Content processing status."""

    status: str = Field(..., description="Current processing status")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list)


class SourceContent(BaseModel):
    """Source content model."""

    id: UUID = Field(..., description="Unique identifier")
    content: Dict[str, str] = Field(..., description="Content fields")
    metadata: SourceContentMetadata
    metrics: Optional[ContentMetrics] = None
    analysis: Optional[ContentAnalysis] = None
    processing_status: ProcessingStatus

    @validator("content")
    def validate_content(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate content fields."""
        required = {"title", "body", "url"}
        if not all(field in v for field in required):
            missing = required - set(v.keys())
            raise ValueError(f"Missing required content fields: {missing}")
        return v


class GenerationMetadata(BaseModel):
    """Metadata for generated content."""

    prompt: str = Field(..., description="Generation prompt used")
    model: str = Field(..., description="AI model used")
    temperature: float = Field(..., ge=0, le=1, description="Generation temperature")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration: int = Field(..., description="Generation duration in ms")
    source_references: List[UUID] = Field(default_factory=list)


class ReviewStatus(BaseModel):
    """Content review status."""

    status: str = Field(..., description="Review status")
    reviewer: Optional[str] = None
    feedback: List[str] = Field(default_factory=list)
    score: Optional[float] = Field(None, ge=0, le=1)
    review_date: Optional[datetime] = None


class PublicationStatus(BaseModel):
    """Content publication status."""

    status: str = Field(..., description="Publication status")
    scheduled_date: Optional[datetime] = None
    published_date: Optional[datetime] = None
    url: Optional[str] = None


class GeneratedContent(BaseModel):
    """Generated content model."""

    id: UUID = Field(..., description="Unique identifier")
    version: int = Field(1, description="Content version")
    content: Dict[str, Any] = Field(..., description="Generated content")
    generation: GenerationMetadata
    review: ReviewStatus
    metrics: Optional[ContentMetrics] = None
    publication: PublicationStatus

    @validator("content")
    def validate_content(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated content fields."""
        required = {"title", "body"}
        if not all(field in v for field in required):
            missing = required - set(v.keys())
            raise ValueError(f"Missing required content fields: {missing}")
        return v


class TrainingSetCriteria(BaseModel):
    """Criteria for training set selection."""

    min_quality_score: float = Field(..., ge=0, le=1)
    min_engagement: int = Field(0, ge=0)
    topics: List[str] = Field(default_factory=list)
    content_types: List[str] = Field(default_factory=list)


class TrainingSetStatus(BaseModel):
    """Training set status."""

    size: int = Field(0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(True)


class TrainingSetPerformance(BaseModel):
    """Training set performance metrics."""

    avg_generation_quality: Optional[float] = Field(None, ge=0, le=1)
    approval_rate: Optional[float] = Field(None, ge=0, le=1)
    engagement_rate: Optional[float] = Field(None, ge=0, le=1)


class TrainingSet(BaseModel):
    """Training set model."""

    id: UUID = Field(..., description="Unique identifier")
    source_content: List[UUID] = Field(..., description="Source content references")
    criteria: TrainingSetCriteria
    status: TrainingSetStatus
    performance: Optional[TrainingSetPerformance] = None


class PromptTemplate(BaseModel):
    """Prompt template model."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(..., description="Template name")
    template: str = Field(..., description="Prompt template")
    variables: List[str] = Field(..., description="Template variables")
    usage: Dict[str, List[str]] = Field(..., description="Usage metadata")
    performance: Dict[str, Union[float, int]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
