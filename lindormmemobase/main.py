#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

from typing import Optional, List
from .config import Config
from .models.profile_topic import ProfileConfig
from .models.blob import Blob
from .models.types import FactResponse, MergeAddResult, Profile, ProfileEntry
from .models.promise import Promise
from .core.extraction.processor.process_blobs import process_blobs


class LindormMemobase:
    """
    Main interface for the LindormMemobase memory extraction system.
    
    This class provides a unified interface for all memory extraction,
    profile management, and search functionality.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize LindormMemobase with user configuration.
        
        Args:
            config: User-provided Config object. If None, loads from default config files.
        """
        self.config = config if config is not None else Config.load_config()
    
    @classmethod
    def from_config(cls, **kwargs):
        """
        Create LindormMemobase instance from configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to override defaults
        
        Returns:
            LindormMemobase instance with custom configuration
            
        Example:
            memobase = LindormMemobase.from_config(
                language="zh",
                llm_api_key="your-api-key",
                best_llm_model="gpt-4o"
            )
        """
        config = create_config(**kwargs)
        return cls(config)
    
    async def process_user_blobs(
        self, 
        user_id: str, 
        blobs: List[Blob], 
        profile_config: Optional[ProfileConfig] = None
    ) -> Promise:
        """
        Process user blobs to extract memory and update profiles.
        
        Args:
            user_id: Unique identifier for the user
            blobs: List of user data blobs to process
            profile_config: Profile configuration. If None, uses default.
            
        Returns:
            Promise containing the processing results
        """
        if profile_config is None:
            profile_config = ProfileConfig()
            
        return await process_blobs(user_id, profile_config, blobs, self.config)
    
    async def extract_memories(
        self, 
        user_id: str, 
        blobs: List[Blob], 
        profile_config: Optional[ProfileConfig] = None
    ) -> Promise:
        """
        Extract memories from user blobs (alias for process_user_blobs).
        
        Args:
            user_id: Unique identifier for the user
            blobs: List of user data blobs to process
            profile_config: Profile configuration. If None, uses default.
            
        Returns:
            Promise containing the extraction results
        """
        return await self.process_user_blobs(user_id, blobs, profile_config)
    
    async def get_user_profiles(self, user_id: str) -> Promise[List[Profile]]:
        """
        Get user profiles from storage.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Promise containing list of user profiles
        """
        # TODO: Implement profile retrieval from storage
        return Promise.resolve([])
    
    
    
    async def get_events(
        self, 
        user_id: str, 
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> Promise[List[dict]]:
        """
        Get events from storage.
        
        Args:
            user_id: Unique identifier for the user
            start_time: Start timestamp filter (optional)
            end_time: End timestamp filter (optional)
            limit: Maximum number of events to return
            
        Returns:
            Promise containing matching events
        """
        # TODO: Implement event retrieval
        return Promise.resolve([])
    
    async def search_events(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 10
    ) -> Promise[List[dict]]:
        """
        Search events by query.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            Promise containing matching events
        """
        # TODO: Implement event search functionality
        return Promise.resolve([])


# Convenience functions for users who want simple interfaces
async def extract_memories(
    user_id: str, 
    blobs: List[Blob], 
    config: Optional[Config] = None,
    profile_config: Optional[ProfileConfig] = None
) -> Promise:
    """
    Simple function to extract memories from user blobs.
    
    Args:
        user_id: Unique identifier for the user  
        blobs: List of user data blobs to process
        config: System configuration. If None, loads from default.
        profile_config: Profile configuration. If None, uses default.
        
    Returns:
        Promise containing the extraction results
    """
    memobase = LindormMemobase(config)
    return await memobase.extract_memories(user_id, blobs, profile_config)


def create_config(**kwargs) -> Config:
    """
    Create a Config object with custom parameters.
    
    Args:
        **kwargs: Configuration parameters to override defaults
        
    Returns:
        Config object with user-specified parameters
        
    Example:
        config = create_config(
            language="zh",
            llm_api_key="your-api-key",
            best_llm_model="gpt-4"
        )
    """
    # Start with an empty config dict and add user parameters
    config_dict = {}
    
    # Add user parameters
    config_dict.update(kwargs)
    
    # Load any additional config from files if they exist, but don't fail if they don't
    try:
        import os
        import yaml
        if os.path.exists("config.yaml"):
            with open("config.yaml") as f:
                base_config = yaml.safe_load(f) or {}
            # User parameters take precedence over file config
            base_config.update(config_dict)
            config_dict = base_config
    except Exception:
        # If loading config file fails, just use user parameters
        pass
    
    # Process environment variables
    config_dict = Config._process_env_vars(config_dict)
    
    # Create Config object with the merged parameters
    # Filter out any keys that aren't in the dataclass fields
    import dataclasses
    fields = {field.name for field in dataclasses.fields(Config)}
    filtered_config = {k: v for k, v in config_dict.items() if k in fields}
    
    return Config(**filtered_config)


# Example usage:
if __name__ == "__main__":
    import asyncio
    from .models.blob import BlobType
    
    async def example_usage():
        # Method 1: Using LindormMemobase.from_config class method
        print("=== Method 1: Using LindormMemobase.from_config ===")
        
        # Initialize LindormMemobase with from_config
        memobase = LindormMemobase.from_config(
            language="en",
            best_llm_model="gpt-4o-mini",
            llm_api_key="test-key"  # In real usage, set this to your API key
        )
        
        print("Initialized LindormMemobase with from_config")
        print(f"Language: {memobase.config.language}")
        print(f"Model: {memobase.config.best_llm_model}")
        
        # Method 2: Using LindormMemobase class directly
        print("\n=== Method 2: Using LindormMemobase class directly ===")
        
        # Create custom config
        my_config = create_config(
            language="zh",
            best_llm_model="gpt-4o"
        )
        
        # Initialize LindormMemobase with custom config
        memobase2 = LindormMemobase(config=my_config)
        print(f"Language: {memobase2.config.language}")
        print(f"Model: {memobase2.config.best_llm_model}")
        
        # Method 3: Using convenience function
        print("\n=== Method 3: Using convenience function ===")
        
        # Create some test blobs
        test_blobs = [
            Blob(
                id="test1",
                content="I love playing tennis on weekends",
                type=BlobType.chat,
                timestamp=1234567890
            )
        ]
        
        # This would process the blobs if we had a working LLM setup
        # result = await extract_memories("user123", test_blobs, my_config)
        print("Would process blobs with user-provided config")
        
        print("\n=== Unified Interface Complete! ===")
        print("All methods available through LindormMemobase class")
        print("Configuration fully controllable by users")
    
    # Run example
    asyncio.run(example_usage())