#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

from typing import Optional, List
from .config import Config
from .models.profile_topic import ProfileConfig
from .models.blob import Blob, OpenAICompatibleMessage
from .models.types import FactResponse, MergeAddResult, Profile, ProfileEntry
from .models.promise import Promise
from .models.response import CODE
from .core.extraction.processor.process_blobs import process_blobs
from .core.search.context import get_user_context
from .core.search.events import get_user_event_gists, search_user_event_gists
from .core.search.user_profiles import get_user_profiles_data, filter_profiles_with_chats
from .core.storage.user_profiles import get_user_profiles


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
    
    async def get_user_profiles(self, user_id: str, topics: Optional[List[str]] = None) -> Promise[List[Profile]]:
        """
        Get user profiles from storage.
        
        Args:
            user_id: Unique identifier for the user
            topics: Optional list of topics to filter by
            
        Returns:
            Promise containing list of user profiles
        """
        try:
            profiles_result = await get_user_profiles(user_id, self.config)
            if not profiles_result.ok():
                return profiles_result
                
            raw_profiles = profiles_result.data()
            
            # Convert ProfileData to Profile format
            profiles = []
            topic_groups = {}
            
            # Group profiles by topic
            for profile_data in raw_profiles.profiles:
                topic = profile_data.attributes.get("topic", "general")
                subtopic = profile_data.attributes.get("sub_topic", "general")
                
                if topics and topic not in topics:
                    continue
                    
                if topic not in topic_groups:
                    topic_groups[topic] = {}
                    
                topic_groups[topic][subtopic] = ProfileEntry(
                    content=profile_data.content,
                    last_updated=profile_data.updated_at.timestamp() if profile_data.updated_at else None
                )
            
            # Convert to Profile objects
            for topic, subtopics in topic_groups.items():
                profiles.append(Profile(
                    topic=topic,
                    subtopics=subtopics
                ))
                
            return Promise.resolve(profiles)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get user profiles: {str(e)}")
    
    
    
    async def get_events(
        self, 
        user_id: str, 
        time_range_in_days: int = 21,
        limit: int = 100
    ) -> Promise[List[dict]]:
        """
        Get recent events from storage.
        
        Args:
            user_id: Unique identifier for the user
            time_range_in_days: Number of days to look back (default: 21)
            limit: Maximum number of events to return
            
        Returns:
            Promise containing matching events
        """
        try:
            result = await get_user_event_gists(
                user_id=user_id,
                config=self.config,
                topk=limit,
                time_range_in_days=time_range_in_days
            )
            
            if not result.ok():
                return result
                
            events_data = result.data()
            events = []
            
            for gist in events_data.gists:
                events.append({
                    "id": gist.get("id"),
                    "content": gist.get("gist_data", {}).get("content", ""),
                    "created_at": gist.get("created_at"),
                    "updated_at": gist.get("updated_at")
                })
                
            return Promise.resolve(events)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get events: {str(e)}")
    
    async def search_events(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21
    ) -> Promise[List[dict]]:
        """
        Search events by query using vector similarity.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query string
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0-1.0)
            time_range_in_days: Number of days to look back
            
        Returns:
            Promise containing matching events with similarity scores
        """
        try:
            result = await search_user_event_gists(
                user_id=user_id,
                query=query,
                config=self.config,
                topk=limit,
                similarity_threshold=similarity_threshold,
                time_range_in_days=time_range_in_days
            )
            
            if not result.ok():
                return result
                
            events_data = result.data()
            events = []
            
            for gist in events_data.gists:
                events.append({
                    "id": gist.get("id"),
                    "content": gist.get("gist_data", {}).get("content", ""),
                    "created_at": gist.get("created_at"),
                    "updated_at": gist.get("updated_at"),
                    "similarity": gist.get("similarity", 0.0)
                })
                
            return Promise.resolve(events)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to search events: {str(e)}")
    
    async def get_relevant_profiles(
        self,
        user_id: str,
        conversation: List[OpenAICompatibleMessage],
        topics: Optional[List[str]] = None,
        max_profiles: int = 10
    ) -> Promise[List[Profile]]:
        """
        Get profiles relevant to current conversation using LLM-based filtering.
        
        Args:
            user_id: Unique identifier for the user
            conversation: List of chat messages to analyze
            topics: Optional list of topics to consider
            max_profiles: Maximum number of relevant profiles to return
            
        Returns:
            Promise containing relevant profiles ranked by relevance
        """
        try:
            result = await get_user_profiles_data(
                user_id=user_id,
                max_profile_token_size=4000,
                prefer_topics=None,
                only_topics=topics,
                max_subtopic_size=None,
                topic_limits={},
                chats=conversation,
                full_profile_and_only_search_event=False,
                global_config=self.config
            )
            
            if not result.ok():
                return result
                
            profile_section, raw_profiles = result.data()
            
            # Convert to Profile format
            profiles = []
            topic_groups = {}
            
            for profile_data in raw_profiles[:max_profiles]:
                topic = profile_data.attributes.get("topic", "general")
                subtopic = profile_data.attributes.get("sub_topic", "general")
                
                if topic not in topic_groups:
                    topic_groups[topic] = {}
                    
                topic_groups[topic][subtopic] = ProfileEntry(
                    content=profile_data.content,
                    last_updated=profile_data.updated_at.timestamp() if profile_data.updated_at else None
                )
            
            for topic, subtopics in topic_groups.items():
                profiles.append(Profile(
                    topic=topic,
                    subtopics=subtopics
                ))
                
            return Promise.resolve(profiles)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get relevant profiles: {str(e)}")
    
    async def get_conversation_context(
        self,
        user_id: str,
        conversation: List[OpenAICompatibleMessage],
        profile_config: Optional[ProfileConfig] = None,
        max_tokens: int = 2000,
        prefer_topics: Optional[List[str]] = None,
        time_range_days: int = 30
    ) -> Promise[str]:
        """
        Generate comprehensive context for conversation including relevant profiles and events.
        
        Args:
            user_id: Unique identifier for the user
            conversation: Current conversation messages
            profile_config: Profile configuration to use
            max_tokens: Maximum tokens for context
            prefer_topics: Topics to prioritize
            time_range_days: Days to look back for events
            
        Returns:
            Promise containing formatted context string
        """
        try:
            if profile_config is None:
                profile_config = ProfileConfig()
                
            result = await get_user_context(
                user_id=user_id,
                profile_config=profile_config,
                global_config=self.config,
                max_token_size=max_tokens,
                prefer_topics=prefer_topics,
                chats=conversation,
                time_range_in_days=time_range_days,
                event_similarity_threshold=0.2,
                profile_event_ratio=0.6
            )
            
            if not result.ok():
                return result
                
            context_data = result.data()
            return Promise.resolve(context_data.context)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get conversation context: {str(e)}")
    
    async def search_profiles(
        self,
        user_id: str,
        query: str,
        topics: Optional[List[str]] = None,
        max_results: int = 10
    ) -> Promise[List[Profile]]:
        """
        Search profiles by text query using conversation context.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query text
            topics: Optional topic filter
            max_results: Maximum number of results
            
        Returns:
            Promise containing matching profiles
        """
        # Create a mock conversation with the query to leverage existing filtering
        mock_conversation = [
            OpenAICompatibleMessage(role="user", content=query)
        ]
        
        return await self.get_relevant_profiles(
            user_id=user_id,
            conversation=mock_conversation,
            topics=topics,
            max_profiles=max_results
        )


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