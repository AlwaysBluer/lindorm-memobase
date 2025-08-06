"""
LindormMemobase - A lightweight memory extraction and profile management system for LLM applications.

This package provides core functionality for:
- Memory extraction from conversations
- User profile management
- Embedding-based search
- Storage backends for events and profiles
"""

__version__ = "0.1.0"

from .main import LindormMemobase, create_config, extract_memories
from .config import Config
from .models.blob import Blob, BlobType
from .models.types import FactResponse, MergeAddResult, Profile, ProfileEntry
from .models.profile_topic import ProfileConfig

__all__ = [
    "LindormMemobase",
    "create_config",
    "extract_memories",
    "Config",
    "ProfileConfig",
    "Blob",
    "BlobType", 
    "FactResponse",
    "MergeAddResult",
    "Profile",
    "ProfileEntry",
]