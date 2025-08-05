"""
LindormMemobase - A lightweight memory extraction and profile management system for LLM applications.

This package provides core functionality for:
- Memory extraction from conversations
- User profile management
- Embedding-based search
- Storage backends for events and profiles
"""

__version__ = "0.1.0"

from .api import MemoBaseAPI
from .config import Config
from .models.blob import Blob
from .models.response import FactResponse, MergeAddResult
from .models.types import Profile, ProfileEntry

__all__ = [
    "MemoBaseAPI",
    "Config", 
    "Blob",
    "FactResponse",
    "MergeAddResult", 
    "Profile",
    "ProfileEntry",
]