"""
LindormMemobase - A lightweight memory extraction and profile management system for LLM applications.

This package provides core functionality for:
- Memory extraction from conversations
- User profile management
- Embedding-based search
- Storage backends for events and profiles
"""

__version__ = "0.1.5"

from lindormmemobase.utils.errors import LindormMemobaseError, ConfigurationError
from lindormmemobase.config import Config
from lindormmemobase.models.blob import Blob, ChatBlob, BlobType
from lindormmemobase.models.types import FactResponse, MergeAddResult, Profile, ProfileEntry
from lindormmemobase.models.profile_topic import ProfileConfig
from lindormmemobase.models.response import EventSearchFilters
from lindormmemobase.main import LindormMemobase

__all__ = [
    "LindormMemobase",
    "LindormMemobaseError",
    "ConfigurationError",
    "Config",
    "ProfileConfig",
    "Blob",
    "ChatBlob",
    "BlobType", 
    "FactResponse",
    "MergeAddResult",
    "Profile",
    "ProfileEntry",
    "EventSearchFilters",
]