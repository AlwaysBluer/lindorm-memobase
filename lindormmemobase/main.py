#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

import os
import yaml
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from .config import Config
from .models.profile_topic import ProfileConfig
from .models.blob import Blob, OpenAICompatibleMessage
from .models.types import  Profile, ProfileEntry
from .core.extraction.processor.process_blobs import process_blobs
from .core.search.context import get_user_context
from .core.search.events import get_user_event_gists, search_user_event_gists
from .core.search.user_profiles import get_user_profiles_data, filter_profiles_with_chats
from .core.storage.user_profiles import get_user_profiles


class LindormMemobaseError(Exception):
    """Base exception class for LindormMemobase errors."""
    pass


class ConfigurationError(LindormMemobaseError):
    """Raised when configuration is invalid or missing."""
    pass


class LindormMemobase:
    """
    Main interface for the LindormMemobase memory extraction system.
    
    This class provides a unified interface for all memory extraction,
    profile management, and search functionality.
    
    Examples:
        # Method 1: Use default configuration
        memobase = LindormMemobase()
        
        # Method 2: From YAML file path
        memobase = LindormMemobase.from_yaml_file("config.yaml")
        
        # Method 3: From parameters
        memobase = LindormMemobase.from_config(llm_api_key="your-key", language="zh")
        
        # Method 4: From Config object
        config = Config.load_config()
        memobase = LindormMemobase(config)
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize LindormMemobase with user configuration.
        
        Args:
            config: User-provided Config object. If None, loads from default config files.
            
        Raises:
            ConfigurationError: If configuration is invalid or cannot be loaded.
        """
        try:
            self.config = config if config is not None else Config.load_config()
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
    
    @classmethod
    def from_yaml_file(cls, config_file_path: Union[str, Path]) -> "LindormMemobase":
        """
        Create LindormMemobase instance from YAML configuration file.
        
        Args:
            config_file_path: Path to YAML configuration file
            
        Returns:
            LindormMemobase instance with configuration from file
            
        Raises:
            ConfigurationError: If file cannot be read or is invalid
            
        Example:
            memobase = LindormMemobase.from_yaml_file("config.yaml")
        """
        try:
            config_path = Path(config_file_path)
            if not config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f) or {}
                
            config = create_config(**config_dict)
            return cls(config)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {str(e)}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from file: {str(e)}") from e
    
    @classmethod
    def from_config(cls, **kwargs) -> "LindormMemobase":
        """
        Create LindormMemobase instance from configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to override defaults
        
        Returns:
            LindormMemobase instance with custom configuration
            
        Raises:
            ConfigurationError: If configuration parameters are invalid
            
        Example:
            memobase = LindormMemobase.from_config(
                language="zh",
                llm_api_key="your-api-key",
                best_llm_model="gpt-4o"
            )
        """
        try:
            config = create_config(**kwargs)
            return cls(config)
        except Exception as e:
            raise ConfigurationError(f"Failed to create configuration from parameters: {str(e)}") from e
    
    
    async def extract_memories(
        self, 
        user_id: str, 
        blobs: List[Blob], 
        profile_config: Optional[ProfileConfig] = None
    ):
        """
        Extract memories from user blobs.
        
        Args:
            user_id: Unique identifier for the user
            blobs: List of user data blobs to process
            profile_config: Profile configuration. If None, uses default.
            
        Returns:
            Extraction results data
            
        Raises:
            LindormMemobaseError: If extraction fails
        """
        try:
            result = await process_blobs(
                user_id=user_id,
                profile_config=profile_config or ProfileConfig(),
                blobs=blobs,
                config=self.config
            )
            
            if result.ok():
                return result.data()
            else:
                raise LindormMemobaseError(f"Memory extraction failed: {result.msg()}")
                
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Memory extraction failed: {str(e)}") from e
    
    async def get_user_profiles(self, user_id: str, topics: Optional[List[str]] = None) -> List[Profile]:
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
                raise LindormMemobaseError(f"Failed to get user profiles: {profiles_result.msg()}")
                
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
                
            return profiles
        except Exception as e:
            raise LindormMemobaseError(f"Failed to get user profiles: {str(e)}") from e
    
    
    async def get_events(
        self, 
        user_id: str, 
        time_range_in_days: int = 21,
        limit: int = 100
    ) -> List[dict]:
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
                raise LindormMemobaseError(f"Failed to get events: {result.msg()}")
                
            events_data = result.data()
            events = []
            
            for gist in events_data.gists:
                events.append({
                    "id": gist.get("id"),
                    "content": gist.get("gist_data", {}).get("content", ""),
                    "created_at": gist.get("created_at"),
                    "updated_at": gist.get("updated_at")
                })
                
            return events
        except Exception as e:
            raise LindormMemobaseError(f"Failed to get events: {str(e)}") from e
    
    async def search_events(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21
    ) -> List[dict]:
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
                raise LindormMemobaseError(f"Failed to search events: {result.msg()}")
                
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
                
            return events
        except Exception as e:
            raise LindormMemobaseError(f"Failed to search events: {str(e)}") from e
    
    async def get_relevant_profiles(
        self,
        user_id: str,
        conversation: List[OpenAICompatibleMessage],
        topics: Optional[List[str]] = None,
        max_profiles: int = 10,
        max_profile_token_size: int = 4000,
        max_subtopic_size: Optional[int] = None,
        topic_limits: Optional[Dict[str, int]] = None,
        full_profile_and_only_search_event: bool = False
    ) -> List[Profile]:
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
                max_profile_token_size=max_profile_token_size,
                prefer_topics=None,
                only_topics=topics,
                max_subtopic_size=max_subtopic_size,
                topic_limits=topic_limits or {},
                chats=conversation,
                full_profile_and_only_search_event=full_profile_and_only_search_event,
                global_config=self.config
            )
            
            if not result.ok():
                raise LindormMemobaseError(f"Failed to get relevant profiles: {result.msg()}")
                
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
                
            return profiles
        except Exception as e:
            raise LindormMemobaseError(f"Failed to get relevant profiles: {str(e)}") from e
    
    async def get_conversation_context(
        self,
        user_id: str,
        conversation: List[OpenAICompatibleMessage],
        profile_config: Optional[ProfileConfig] = None,
        max_token_size: int = 2000,
        prefer_topics: Optional[List[str]] = None,
        time_range_in_days: int = 30,
        event_similarity_threshold: float = 0.2,
        profile_event_ratio: float = 0.6,
        only_topics: Optional[List[str]] = None,
        max_subtopic_size: Optional[int] = None,
        topic_limits: Optional[Dict[str, int]] = None,
        require_event_summary: bool = False,
        customize_context_prompt: Optional[str] = None,
        full_profile_and_only_search_event: bool = False,
        fill_window_with_events: bool = False
    ) -> str:
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
                max_token_size=max_token_size,
                prefer_topics=prefer_topics,
                only_topics=only_topics,
                max_subtopic_size=max_subtopic_size,
                topic_limits=topic_limits or {},
                chats=conversation,
                time_range_in_days=time_range_in_days,
                event_similarity_threshold=event_similarity_threshold,
                profile_event_ratio=profile_event_ratio,
                require_event_summary=require_event_summary,
                customize_context_prompt=customize_context_prompt,
                full_profile_and_only_search_event=full_profile_and_only_search_event,
                fill_window_with_events=fill_window_with_events
            )
            
            if not result.ok():
                raise LindormMemobaseError(f"Failed to get conversation context: {result.msg()}")
                
            context_data = result.data()
            return context_data.context
        except Exception as e:
            raise LindormMemobaseError(f"Failed to get conversation context: {str(e)}") from e
    
    async def search_profiles(
        self,
        user_id: str,
        query: str,
        topics: Optional[List[str]] = None,
        max_results: int = 10
    ) -> List[Profile]:
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
    


def create_config(**kwargs) -> Config:
    """
    Create a Config object with custom parameters.
    
    Args:
        **kwargs: Configuration parameters to override defaults
        
    Returns:
        Config object with user-specified parameters
        
    Raises:
        ConfigurationError: If configuration parameters are invalid
        
    Example:
        config = create_config(
            language="zh",
            llm_api_key="your-api-key",
            best_llm_model="gpt-4"
        )
    """
    try:
        # Start with an empty config dict and add user parameters
        config_dict = {}
        
        # Add user parameters
        config_dict.update(kwargs)
        
        # Load any additional config from files if they exist, but don't fail if they don't
        try:
            if os.path.exists("config.yaml"):
                with open("config.yaml", 'r', encoding='utf-8') as f:
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
    except Exception as e:
        raise ConfigurationError(f"Failed to create configuration: {str(e)}") from e
