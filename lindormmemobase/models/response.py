from datetime import datetime
from enum import IntEnum
from typing import Optional, Literal, Any
from pydantic import BaseModel, UUID4, UUID5, Field
UUID = UUID4 | UUID5


class CODE(IntEnum):
    SUCCESS = 0
    BAD_REQUEST = 400
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    UNPROCESSABLE_ENTITY = 422
    SERVER_PARSE_ERROR = 1001
    SERVER_PROCESS_ERROR = 1002
    LLM_ERROR = 1003


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
    id: UUID = Field(..., description="The profile's unique identifier")
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
    event_id: Optional[UUID] = Field(..., description="The event's unique identifier")
    add_profiles: Optional[list[UUID]] = Field(
        ..., description="List of added profiles' ids"
    )
    update_profiles: Optional[list[UUID]] = Field(
        ..., description="List of updated profiles' ids"
    )
    delete_profiles: Optional[list[UUID]] = Field(
        ..., description="List of deleted profiles' ids"
    )

class UserProfilesData(BaseModel):
    profiles: list[ProfileData] = Field(..., description="List of user profiles")

class IdsData(BaseModel):
    ids: list[UUID] = Field(..., description="List of UUID identifiers")

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
    id: UUID = Field(..., description="The event's unique identifier")
    event_data: EventData = Field(None, description="User event data in JSON")
    created_at: datetime = Field(
        None, description="Timestamp when the event was created"
    )
    updated_at: datetime = Field(
        None, description="Timestamp when the event was last updated"
    )
    similarity: Optional[float] = Field(None, description="Similarity score")

