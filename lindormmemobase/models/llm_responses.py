"""Pydantic response models for LLM JSON Mode.

These models are used for validating structured LLM responses when using
JSON Mode with response_format={"type": "json_object"}.
"""

from typing import Literal, List
from pydantic import BaseModel, Field


class MergeProfileResponse(BaseModel):
    """Response for merge_profile LLM call.

    The LLM decides whether to APPEND new info, UPDATE existing memo,
    or ABORT if the new info is redundant/irrelevant.
    """
    action: Literal["UPDATE", "APPEND", "ABORT"] = Field(
        ...,
        description="Action to take: UPDATE (rewrite memo), APPEND (add new), ABORT (skip)"
    )
    memo: str = Field(
        ...,
        description="For UPDATE: complete rewritten memo; For APPEND/ABORT: the action keyword"
    )


class EventTaggingItem(BaseModel):
    """Single event tag item."""
    tag: str = Field(..., description="Tag name")
    value: str = Field(..., description="Tag value")


class EventTaggingResponse(BaseModel):
    """Response for event_tagging LLM call.

    Extracts structured tags from user events.
    """
    tags: List[EventTaggingItem] = Field(
        default_factory=list,
        description="List of extracted tags"
    )


class OrganizeProfileItem(BaseModel):
    """Single organized profile subtopic item."""
    sub_topic: str = Field(..., description="Subtopic name")
    memo: str = Field(..., description="Organized memo content")


class OrganizeProfileResponse(BaseModel):
    """Response for organize_profile LLM call.

    Organizes and restructures user profiles by subtopics.
    """
    subtopics: List[OrganizeProfileItem] = Field(
        default_factory=list,
        description="List of organized subtopics with their memos"
    )
