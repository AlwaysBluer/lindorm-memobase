"""Exception classes for LindormMemobase.

This module defines a hierarchy of exceptions used throughout the library.
All exceptions inherit from LindormMemobaseError for easy catching.
"""

from typing import Optional
from ..models.response import CODE


class LindormMemobaseError(Exception):
    """Base exception for all LindormMemobase errors.
    
    Attributes:
        message: Error message
        error_code: Optional CODE enum for backward compatibility
    """
    
    def __init__(self, message: str, error_code: Optional[CODE] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or CODE.INTERNAL_SERVER_ERROR
    
    def __str__(self):
        return self.message


class ConfigurationError(LindormMemobaseError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.BAD_REQUEST)


class ValidationError(LindormMemobaseError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.UNPROCESSABLE_ENTITY)


class StorageError(LindormMemobaseError):
    """Base exception for storage layer failures."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.SERVER_PROCESS_ERROR)


class BufferStorageError(StorageError):
    """Raised when buffer storage operations fail."""
    pass


class TableStorageError(StorageError):
    """Raised when table storage operations fail."""
    pass


class SearchStorageError(StorageError):
    """Raised when search storage operations fail."""
    pass


class ExtractionError(LindormMemobaseError):
    """Base exception for memory extraction failures."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.SERVER_PROCESS_ERROR)


class MergeError(ExtractionError):
    """Raised when profile merging fails."""
    pass


class OrganizeError(ExtractionError):
    """Raised when profile organization fails."""
    pass


class ProcessingError(ExtractionError):
    """Raised when blob processing fails."""
    pass


class SearchError(LindormMemobaseError):
    """Raised when search operations fail."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.SERVER_PROCESS_ERROR)


class LLMError(LindormMemobaseError):
    """Raised when LLM API calls fail."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.LLM_ERROR)


class EmbeddingError(LindormMemobaseError):
    """Raised when embedding generation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, CODE.SERVER_PROCESS_ERROR)


class ExternalAPIError(Exception):
    """Legacy exception for external API errors."""
    pass


def exception_to_code(exc: Exception) -> CODE:
    """Convert an exception to a CODE enum for backward compatibility.
    
    Args:
        exc: Exception instance
        
    Returns:
        CODE enum value
        
    Examples:
        >>> exception_to_code(ConfigurationError("Invalid config"))
        CODE.BAD_REQUEST
        >>> exception_to_code(StorageError("DB error"))
        CODE.SERVER_PROCESS_ERROR
    """
    if isinstance(exc, LindormMemobaseError):
        return exc.error_code
    elif isinstance(exc, (ConfigurationError,)):
        return CODE.BAD_REQUEST
    elif isinstance(exc, ValidationError):
        return CODE.UNPROCESSABLE_ENTITY
    elif isinstance(exc, LLMError):
        return CODE.LLM_ERROR
    elif isinstance(exc, (StorageError, ExtractionError, SearchError, EmbeddingError)):
        return CODE.SERVER_PROCESS_ERROR
    else:
        return CODE.INTERNAL_SERVER_ERROR
