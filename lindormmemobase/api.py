#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

from config import Config
from models.profile_topic import ProfileConfig
from models.blob import Blob
from utils.promise import Promise
from core.extraction.processor.process_blobs import process_blobs


class LindormMemobase:
    """
    Main interface for the LindormMemobase memory extraction system.
    Users can initialize this with their own configuration.
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize LindormMemobase with user configuration.
        
        Args:
            config: User-provided Config object. If None, loads from default config files.
        """
        self.config = config if config is not None else Config.load_config()
    
    async def process_user_blobs(
        self, 
        user_id: str, 
        blobs: list[Blob], 
        profile_config: ProfileConfig = None
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


# Convenience functions for users who want simple interfaces
async def extract_memories(
    user_id: str, 
    blobs: list[Blob], 
    config: Config = None,
    profile_config: ProfileConfig = None
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
    if config is None:
        config = Config.load_config()
    if profile_config is None:
        profile_config = ProfileConfig()
        
    return await process_blobs(user_id, profile_config, blobs, config)


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
    # Load base config from files
    base_config = Config.load_config()
    
    # Override with user parameters
    for key, value in kwargs.items():
        if hasattr(base_config, key):
            setattr(base_config, key, value)
    
    return base_config


# Example usage:
if __name__ == "__main__":
    import asyncio
    from models.blob import BlobType
    
    async def example_usage():
        # Method 1: Using LindormMemobase class
        print("=== Method 1: Using LindormMemobase class ===")
        
        # Create custom config
        my_config = create_config(
            language="en",
            best_llm_model="gpt-4o-mini"
        )
        
        # Initialize LindormMemobase with custom config
        memobase = LindormMemobase(config=my_config)
        
        # Create some test blobs
        test_blobs = [
            Blob(
                id="test1",
                content="I love playing tennis on weekends",
                type=BlobType.chat,
                timestamp=1234567890
            )
        ]
        
        print("Initialized LindormMemobase with custom config")
        print(f"Language: {my_config.language}")
        print(f"Model: {my_config.best_llm_model}")
        
        # Method 2: Using convenience function
        print("\n=== Method 2: Using convenience function ===")
        
        # This would process the blobs if we had a working LLM setup
        # result = await extract_memories("user123", test_blobs, my_config)
        print("Would process blobs with user-provided config")
        
        print("\n=== Config is now user-controllable! ===")
        print("No more global CONFIG variable")
        print("Users have full control over configuration")
    
    # Run example
    asyncio.run(example_usage())