from datetime import datetime
from enum import IntEnum
from typing import Optional, Any, List, Generic, TypeVar, Union

import numpy as np
from pydantic import BaseModel, Field, field_validator


class CODE(IntEnum):
    SUCCESS = 0
    BAD_REQUEST = 400
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    UNPROCESSABLE_ENTITY = 422
    SERVER_PARSE_ERROR = 1001
    SERVER_PROCESS_ERROR = 1002
    LLM_ERROR = 1003
    NOT_IMPLEMENTED = 1004


class BaseResponse(BaseModel):
    errno: CODE = Field(default=CODE.SUCCESS, description="Error code")
    errmsg: str = Field(default="", description="Error message")
    data: Any = Field(default=None, description="Response data")


class AIUserProfile(BaseModel):
    topic: str = Field(..., description="The main topic of the user profile")
    sub_topic: str = Field(..., description="The sub-topic of the user profile")
    memo: str = Field(..., description="The memo content of the user profile")


class AIUserProfiles(BaseModel):
    facts: list[AIUserProfile] = Field(..., description="List of user profile facts")


class ProfileData(BaseModel):
    id: str = Field(..., description="The profile's unique identifier")
    content: str = Field(..., description="User profile content value")
    created_at: datetime = Field(
        None, description="Timestamp when the profile was created"
    )
    updated_at: datetime = Field(
        None, description="Timestamp when the profile was last updated"
    )
    attributes: Optional[dict] = Field(
        None,
        description="User profile attributes in JSON, containing 'topic', 'sub_topic'",
    )


class ChatModalResponse(BaseModel):
    event_id: str = Field(..., description="The event's unique identifier")
    add_profiles: Optional[list[str]] = Field(
        ..., description="List of added profiles' ids"
    )
    update_profiles: Optional[list[str]] = Field(
        ..., description="List of updated profiles' ids"
    )
    delete_profiles: Optional[list[str]] = Field(
        ..., description="List of deleted profiles' ids"
    )



class UserProfilesData(BaseModel):
    profiles: list[ProfileData] = Field(..., description="List of user profiles")


class IdsData(BaseModel):
    ids: list[str] = Field(..., description="List of identifiers")


class ProfileDelta(BaseModel):
    content: str = Field(..., description="The profile content")
    attributes: Optional[dict] = Field(
        ...,
        description="User profile attributes in JSON, containing 'topic', 'sub_topic'",
    )


class EventTag(BaseModel):
    tag: str = Field(..., description="The event tag")
    value: str = Field(..., description="The event tag value")


class EventData(BaseModel):
    profile_delta: Optional[list[ProfileDelta]] = Field(
        None, description="List of profile data"
    )
    event_tip: Optional[str] = Field(None, description="Event tip")
    event_tags: Optional[list[EventTag]] = Field(None, description="List of event tags")


class ProfileDelta(BaseModel):
    content: str = Field(..., description="The profile content")
    attributes: Optional[dict] = Field(
        ...,
        description="User profile attributes in JSON, containing 'topic', 'sub_topic'",
    )


class EventTag(BaseModel):
    tag: str = Field(..., description="The event tag")
    value: str = Field(..., description="The event tag value")


class EventGistData(BaseModel):
    content: str = Field(..., description="The event gist content")


class EventData(BaseModel):
    profile_delta: Optional[list[ProfileDelta]] = Field(
        None, description="List of profile data"
    )
    event_tip: Optional[str] = Field(None, description="Event tip")
    event_tags: Optional[list[EventTag]] = Field(None, description="List of event tags")


class UserEventData(BaseModel):
    id: str = Field(..., description="The event's unique identifier")
    event_data: EventData = Field(None, description="User event data in JSON")
    created_at: datetime = Field(
        None, description="Timestamp when the event was created"
    )
    updated_at: datetime = Field(
        None, description="Timestamp when the event was last updated"
    )
    similarity: Optional[float] = Field(None, description="Similarity score")


class ImageData(BaseModel):
    """Image data model for storage and retrieval."""
    image_id: str = Field(..., description="The image's unique identifier")
    project_id: str = Field(..., description="Project identifier")
    user_id: str = Field(..., description="User identifier")
    caption: Optional[str] = Field(None, description="Image caption")
    image_url: Optional[str] = Field(None, description="Image URL")
    image_data: Optional[bytes] = Field(None, description="Raw image bytes")
    content_type: Optional[str] = Field(None, description="Image MIME type")
    file_size: Optional[int] = Field(None, description="Image size in bytes")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")
    similarity: Optional[float] = Field(None, description="Similarity score")

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def parse_datetime(cls, v: Union[str, datetime, None]) -> Optional[datetime]:
        """Parse datetime from string or datetime object."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try common formats
            for fmt in (
                '%Y-%m-%dT%H:%M:%S.%f%z',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
            ):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            # Fallback: try fromisoformat
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                pass
        return v


class ImageInput(BaseModel):
    """Input model for adding images."""
    image_url: Optional[str] = Field(None, description="Image URL (preferred)")
    image_data: Optional[bytes] = Field(None, description="Image binary data")
    caption: Optional[str] = Field(None, description="Image caption")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class ImageResult(BaseModel):
    """Result model for image add/update operations.

    Note: image_id is Optional[str] to support partial failure scenarios
    in batch operations where individual items may fail.
    """
    image_id: Optional[str] = Field(None, description="The image's unique identifier (None if operation failed)")
    caption: Optional[str] = Field(None, description="Generated or provided caption")
    success: bool = Field(True, description="Whether the operation succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class ImageSearchFilters(BaseModel):
    """Image search filter conditions."""
    time_from: Optional[datetime] = Field(None, description="Start time filter")
    time_to: Optional[datetime] = Field(None, description="End time filter")
    content_types: Optional[List[str]] = Field(None, description="Filter by content types")
    metadata_filters: Optional[dict] = Field(None, description="Filter by metadata fields")


T = TypeVar('T')


class PagedResult(BaseModel, Generic[T]):
    """Paginated result wrapper."""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether there are more pages")


class ResetResult(BaseModel):
    """Result model for reset operations."""
    deleted_count: int = Field(..., description="Number of deleted items")
    success: bool = Field(True, description="Whether the operation succeeded")


class ContextData(BaseModel):
    context: str = Field(..., description="Context string")


class UserEventGistData(BaseModel):
    id: str = Field(..., description="The event gist's unique identifier (composite key from Lindorm Search)")
    gist_data: EventGistData = Field(None, description="User event gist data")
    created_at: datetime = Field(
        None, description="Timestamp when the event gist was created"
    )
    updated_at: datetime = Field(
        None, description="Timestamp when the event gist was last updated"
    )
    similarity: Optional[float] = Field(None, description="Similarity score")


class UserEventGistsData(BaseModel):
    gists: list[UserEventGistData] = Field(..., description="List of user event gists")


class EventSearchFilters(BaseModel):
    """Event search filter conditions.
    
    This class encapsulates filtering options for advanced event search.
    Filters within the same dimension use OR logic, while different dimensions
    use AND logic.
    
    Attributes:
        project_id: Optional project filter
        time_range_in_days: Number of days to look back (default: 21)
        topics: Filter by profile delta topics (OR logic if multiple)
        subtopics: Filter by profile delta subtopics (OR logic if multiple)
        tags: Filter by event tag names (OR logic if multiple)
        tag_values: Filter by event tag values (OR logic if multiple)
    
    Examples:
        # Filter by single topic
        filters = EventSearchFilters(topics=["life_plan"])
        
        # Filter by topic and subtopic
        filters = EventSearchFilters(
            topics=["life_plan"],
            subtopics=["travel", "career"],
            time_range_in_days=30
        )
        
        # Complex multi-dimensional filtering
        filters = EventSearchFilters(
            project_id="my_project",
            topics=["life_plan", "interests"],
            tags=["preference"],
            time_range_in_days=60
        )
    """
    project_id: Optional[str] = Field(default=None, description="Project identifier filter")
    time_range_in_days: int = Field(default=21, description="Number of days to look back from now")
    topics: Optional[List[str]] = Field(default=None, description="Filter by profile delta topics (OR logic)")
    subtopics: Optional[List[str]] = Field(default=None, description="Filter by profile delta subtopics (OR logic)")
    tags: Optional[List[str]] = Field(default=None, description="Filter by event tag names (OR logic)")
    tag_values: Optional[List[str]] = Field(default=None, description="Filter by event tag values (OR logic)")
