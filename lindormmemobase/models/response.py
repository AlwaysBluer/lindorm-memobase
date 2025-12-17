from datetime import datetime
from enum import IntEnum
from typing import Optional, Any, List

import numpy as np
from pydantic import BaseModel, Field


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
