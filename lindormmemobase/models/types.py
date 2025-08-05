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