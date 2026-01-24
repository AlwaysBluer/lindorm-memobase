"""
Enum definitions for type-safe configuration and API usage.
"""

from enum import StrEnum


class ImageStorageType(StrEnum):
    """Image storage type options."""
    URL = "url"
    BINARY = "binary"
    BOTH = "both"


class MultimodalEmbeddingProvider(StrEnum):
    """Multimodal embedding provider options."""
    LINDORMAI = "lindormai"
    DASHSCOPE = "dashscope"


class VLModelProvider(StrEnum):
    """Vision-Language model provider options."""
    LINDORMAI = "lindormai"
    DASHSCOPE = "dashscope"


class SearchMode(StrEnum):
    """Image search mode options."""
    CAPTION = "caption"
    EMBEDDING = "embedding"
    HYBRID = "hybrid"


class MultimodalInputType(StrEnum):
    """Multimodal embedding input type options."""
    IMAGE = "image"
    TEXT = "text"
