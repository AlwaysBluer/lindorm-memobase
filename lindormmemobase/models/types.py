from typing import TypedDict, Optional, Literal
from dataclasses import dataclass, field
from .response import ProfileData

FactResponse = TypedDict("FactResponse", {"topic": str, "sub_topic": str, "memo": str})
UpdateResponse = TypedDict("UpdateResponse", {"action": str, "memo": str})

Attributes = TypedDict("Attributes", {"topic": str, "sub_topic": str})
AddProfile = TypedDict("AddProfile", {"content": str, "attributes": Attributes})
UpdateProfile = TypedDict(
    "UpdateProfile",
    {"profile_id": str, "content": str, "attributes": Attributes},
)

MergeAddResult = TypedDict(
    "MergeAddResult",
    {
        "add": list[AddProfile],
        "update": list[UpdateProfile],
        "delete": list[str],
        "update_delta": list[AddProfile],
        "before_profiles": list[ProfileData],  # Add missing field
    },
)

# Profile models for the main API
@dataclass
class ProfileEntry:
    """A single entry in a user profile."""
    content: str
    confidence: float = 1.0
    last_updated: Optional[float] = None


@dataclass  
class Profile:
    """A user profile organized by topics and subtopics."""
    topic: str
    subtopics: dict[str, ProfileEntry] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)