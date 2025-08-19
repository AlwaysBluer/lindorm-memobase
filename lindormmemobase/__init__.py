"""
LindormMemobase - A lightweight memory extraction and profile management system for LLM applications.

This package provides core functionality for:
- Memory extraction from conversations
- User profile management
- Embedding-based search
- Storage backends for events and profiles
"""

__version__ = "0.1.4"

from .main import LindormMemobase, LindormMemobaseError, ConfigurationError
from .config import Config
from .models.blob import Blob, ChatBlob, BlobType
from .models.types import FactResponse, MergeAddResult, Profile, ProfileEntry
from .models.profile_topic import ProfileConfig

__all__ = [
    "LindormMemobaseError",
    "ConfigurationError",
    "LindormMemobase",
    "Config",
    "ProfileConfig",
    "Blob",
    "ChatBlob",
    "BlobType", 
    "FactResponse",
    "MergeAddResult",
    "Profile",
    "ProfileEntry",
]