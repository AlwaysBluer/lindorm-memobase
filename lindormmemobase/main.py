#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

import yaml
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from lindormmemobase.config import Config, LOG
from lindormmemobase.models.profile_topic import ProfileConfig
from lindormmemobase.models.blob import Blob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.response import (
    UserEventGistData,
    UserEventData,
    EventSearchFilters,
    MergeOperationResult,
)
from lindormmemobase.models.types import Profile
from lindormmemobase.core.extraction.processor.process_blobs import process_blobs
from lindormmemobase.core.search.context import get_user_context
from lindormmemobase.core.search.events import get_user_events, search_user_events
from lindormmemobase.core.search.event_gists import get_user_event_gists_by_sql, search_user_event_gists
from lindormmemobase.core.search.user_profiles import get_user_profiles_data
from lindormmemobase.core.storage.user_profiles import get_user_profiles
from lindormmemobase.core.storage.buffers import (
    insert_blob_to_buffer,
    detect_buffer_full_or_not,
    flush_buffer_by_ids,
    flush_buffer
)
from lindormmemobase.core.constants import BufferStatus
from lindormmemobase.utils.errors import LindormMemobaseError, ConfigurationError
from lindormmemobase.utils.profiles import convert_profile_data_to_profiles



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
            # Initialize storage layer
            self._init_storage_sync()
            # Lazy initialization of TopicConfigStorage
            self._topic_config_storage: Optional['TopicConfigStorage'] = None
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e

    def _init_storage_sync(self):
        """Initialize storage synchronously (runs async init in background)."""
        from .core.storage.manager import StorageManager
        if not StorageManager.is_initialized():
            try:
                # Try to get running event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context, schedule initialization
                    asyncio.create_task(StorageManager.initialize(self.config))
                else:
                    # No running loop, run synchronously
                    loop.run_until_complete(StorageManager.initialize(self.config))
            except RuntimeError:
                # No event loop exists, create new one
                asyncio.run(StorageManager.initialize(self.config))

    async def initialize_storage(self):
        """
        Initialize storage layer asynchronously.

        This method can be called explicitly to ensure storage is initialized
        before performing operations.
        """
        from .core.storage.manager import StorageManager
        if not StorageManager.is_initialized():
            await StorageManager.initialize(self.config)

    @property
    def topic_config_storage(self) -> 'TopicConfigStorage':
        """Lazy initialization of TopicConfigStorage."""
        if self._topic_config_storage is None:
            from .core.storage.manager import StorageManager
            self._topic_config_storage = StorageManager.get_topic_config_storage(self.config)
        return self._topic_config_storage

    async def invalidate_project_config_cache(self, project_id: Optional[str] = None) -> None:
        """
        Invalidate cache for project config.

        Args:
            project_id: Specific project ID to invalidate. If None, invalidates all.
        """
        self.topic_config_storage.invalidate_cache(project_id)

    async def set_project_config(
        self,
        project_id: str,
        profile_config: ProfileConfig
    ) -> None:
        """
        Set or update ProfileConfig for a specific project in the database.

        This stores the configuration in the ProjectProfileConfigs table,
        which will be automatically loaded when extract_memories() or
        process_buffer() is called with this project_id.

        Args:
            project_id: Project identifier (e.g., 'education_app', 'ecommerce')
            profile_config: ProfileConfig object to store

        Raises:
            LindormMemobaseError: If operation fails

        Example:
            config = ProfileConfig(
                language="zh",
                overwrite_user_profiles=[{
                    "topic": "学习偏好",
                    "sub_topics": [{"name": "学习时间"}]
                }]
            )
            await memobase.set_project_config("education_app", config)
        """
        try:
            await self.topic_config_storage.set_profile_config(project_id, profile_config)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to set project config: {str(e)}") from e

    async def delete_project_config(self, project_id: str) -> bool:
        """
        Delete ProfileConfig for a specific project from the database.

        After deletion, extract_memories() will fall back to config.yaml
        for this project_id.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted, False if config was not found

        Raises:
            LindormMemobaseError: If operation fails

        Example:
            deleted = await memobase.delete_project_config("education_app")
        """
        try:
            return await self.topic_config_storage.delete_profile_config(project_id)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to delete project config: {str(e)}") from e

    async def get_project_config(self, project_id: str) -> Optional[ProfileConfig]:
        """
        Get ProfileConfig for a specific project from the database.

        This method retrieves the current configuration stored in the database,
        bypassing the cache. Returns None if no config exists for the project.

        Args:
            project_id: Project identifier

        Returns:
            ProfileConfig object if found in DB, None otherwise

        Raises:
            LindormMemobaseError: If operation fails

        Example:
            config = await memobase.get_project_config("education_app")
            if config:
                print(f"Language: {config.language}")
                print(f"Topics: {config.overwrite_user_profiles}")
        """
        try:
            # Invalidate cache first to ensure fresh read
            self.topic_config_storage.invalidate_cache(project_id)
            return await self.topic_config_storage.get_profile_config(project_id)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to get project config: {str(e)}") from e

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
                
            config = Config.from_yaml_file(config_path)
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
            from dataclasses import fields
            valid_fields = {f.name for f in fields(Config)}
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
            
            config = Config(**filtered_kwargs)
            return cls(config)
        except Exception as e:
            raise ConfigurationError(f"Failed to create configuration from parameters: {str(e)}") from e
    
    
    async def extract_memories(
        self,
        user_id: str,
        blobs: List[Blob],
        profile_config: Optional[ProfileConfig] = None,
        project_id: Optional[str] = None,
    ):
        """
        Extract memories from user blobs.

        Profile config is resolved in this order:
        1. Explicitly provided profile_config parameter
        2. Project-specific config from database
        3. Global config from config.yaml (fallback)

        Args:
            user_id: Unique identifier for the user
            blobs: List of user data blobs to process
            profile_config: Profile configuration. If None, uses DB or default.
            project_id: Project identifier for multi-tenancy. If None, uses default.

        Returns:
            Extraction results data

        Raises:
            LindormMemobaseError: If extraction fails
        """
        try:
            from .utils.profile_config_resolver import resolve_profile_config

            # Resolve profile config (handles DB lookup and fallback)
            resolved_config = await resolve_profile_config(
                project_id=project_id,
                user_config=profile_config,
                topic_config_storage=self.topic_config_storage,
                main_config=self.config
            )

            return await process_blobs(
                user_id=user_id,
                profile_config=resolved_config,
                blobs=blobs,
                config=self.config,
                project_id=project_id
            )
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Memory extraction failed: {str(e)}") from e
    

    async def get_user_profiles(
        self, 
        user_id: str, 
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None
    ) -> List[Profile]:
        """
        Get user profiles from storage.
        
        Args:
            user_id: Unique identifier for the user
            topics: Optional list of topics to filter by. If provided, only profiles 
                   with matching topics will be returned.
            subtopics: Optional list of subtopics to filter by
            project_id: Optional project ID to filter by. None returns all projects.
            time_from: Optional start time filter (created_at >= time_from)
            time_to: Optional end time filter (created_at <= time_to)
            
        Returns:
            List of user profiles grouped by topic and subtopic
            
        Raises:
            LindormMemobaseError: If profile retrieval fails
            
        Example:
            profiles = await memobase.get_user_profiles(
                "user123", 
                topics=["interests", "preferences"],
                project_id="my_project"
            )
        """
        try:
            raw_profiles_data = await get_user_profiles(
                user_id, 
                self.config,
                project_id=project_id,
                topics=topics,
                subtopics=subtopics,
                time_from=time_from,
                time_to=time_to
            )
            return convert_profile_data_to_profiles(raw_profiles_data.profiles, self.config.profile_split_delimiter, None)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to get user profiles: {str(e)}") from e
    
    async def get_user_event_gists(
        self, 
        user_id: str, 
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        max_token_size: Optional[int] = None
    ) -> List[UserEventGistData]:
        """
        Get user event gists from storage using SQL-based time range queries.
        
        This method retrieves event gists without requiring vector embeddings,
        making it suitable for simple time-based retrieval scenarios.
        
        Args:
            user_id: Unique identifier for the user
            project_id: Optional project filter. If None, returns gists from all projects.
            time_range_in_days: Number of days to look back from now (default: 21)
            limit: Maximum number of gists to return (default: 20)
            max_token_size: Optional token budget to limit total content size
            
        Returns:
            List of UserEventGistData objects, ordered by created_at DESC
            
        Raises:
            LindormMemobaseError: If retrieval fails
            
        Example:
            # Get recent gists for a user
            gists = await memobase.get_user_event_gists(
                "user123",
                time_range_in_days=7,
                limit=10
            )
            
            # Get gists for a specific project with token budget
            gists = await memobase.get_user_event_gists(
                "user123",
                project_id="my_project",
                max_token_size=1000
            )
        """
        try:
            result = await get_user_event_gists_by_sql(
                user_id=user_id,
                config=self.config,
                project_id=project_id,
                time_range_in_days=time_range_in_days,
                limit=limit,
                max_token_size=max_token_size
            )
            return result.gists
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to get user event gists: {str(e)}") from e
    
    
    async def get_user_events(
        self, 
        user_id: str, 
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        max_token_size: Optional[int] = None
    ) -> List[UserEventData]:
        """
        Get user events from storage using SQL-based time range queries.
        
        This method retrieves full events (not just gists) without requiring
        vector embeddings, making it suitable for simple time-based retrieval.
        
        Args:
            user_id: Unique identifier for the user
            project_id: Optional project filter. If None, returns events from all projects.
            time_range_in_days: Number of days to look back from now (default: 21)
            limit: Maximum number of events to return (default: 20)
            max_token_size: Optional token budget to limit total content size
            
        Returns:
            List of UserEventData objects, ordered by created_at DESC
            
        Raises:
            LindormMemobaseError: If retrieval fails
            
        Example:
            # Get recent events for a user
            events = await memobase.get_user_events(
                "user123",
                time_range_in_days=14,
                limit=15
            )
            
            # Get events for a specific project
            events = await memobase.get_user_events(
                "user123",
                project_id="my_project",
                max_token_size=2000
            )
        """
        try:
            result = await get_user_events(
                user_id=user_id,
                config=self.config,
                project_id=project_id,
                time_range_in_days=time_range_in_days,
                limit=limit,
                max_token_size=max_token_size
            )
            return result
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to get user events: {str(e)}") from e
    
    async def search_events(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: Optional[str] = None
    ) -> List[UserEventData]:
        """
        Search events by query using vector similarity.
        
        This method performs semantic search on event embeddings to find
        the most relevant events matching the query.
        
        Args:
            user_id: Unique identifier for the user
            query: Text query to search for
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score 0.0-1.0 (default: 0.2)
            time_range_in_days: Number of days to look back (default: 21)
            project_id: Optional project filter. If None, searches all projects.
            
        Returns:
            List of UserEventData objects with similarity scores, ordered by relevance
            
        Raises:
            LindormMemobaseError: If search fails or embeddings are not enabled
            
        Example:
            # Search for cooking-related events
            events = await memobase.search_events(
                "user123",
                "recipes and cooking tips",
                limit=5,
                similarity_threshold=0.3
            )
            
            # Search within a specific project
            events = await memobase.search_events(
                "user123",
                "machine learning algorithms",
                project_id="ml_project",
                time_range_in_days=30
            )
        """
        try:
            result = await search_user_events(
                user_id=user_id,
                query=query,
                config=self.config,
                topk=limit,
                similarity_threshold=similarity_threshold,
                time_range_in_days=time_range_in_days,
                project_id=project_id
            )
            return result
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to search events: {str(e)}") from e
    
    async def search_events_advanced(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.2,
        filters: Optional[EventSearchFilters] = None
    ) -> List[UserEventData]:
        """Search events with advanced filtering capabilities.
        
        This method extends search_events with support for topic, subtopic,
        and tag-based filtering.
        
        Args:
            user_id: Unique identifier for the user
            query: Text query for semantic search
            limit: Maximum number of results (default: 10)
            similarity_threshold: Minimum similarity score 0.0-1.0 (default: 0.2)
            filters: Optional EventSearchFilters for fine-grained filtering
            
        Returns:
            List of UserEventData objects with similarity scores
            
        Raises:
            LindormMemobaseError: If search fails or embeddings are not enabled
            
        Example:
            # Search for travel-related events in life_plan topic
            filters = EventSearchFilters(
                topics=["life_plan"],
                subtopics=["travel"],
                time_range_in_days=30
            )
            events = await memobase.search_events_advanced(
                user_id="user123",
                query="European travel plans",
                limit=20,
                similarity_threshold=0.3,
                filters=filters
            )
            
            # Search for events with specific tags
            filters = EventSearchFilters(
                tags=["interest", "hobby"],
                project_id="my_project"
            )
            events = await memobase.search_events_advanced(
                user_id="user123",
                query="cooking recipes",
                filters=filters
            )
        """
        if filters is None:
            filters = EventSearchFilters()
        
        try:
            result = await search_user_events(
                user_id=user_id,
                query=query,
                config=self.config,
                topk=limit,
                similarity_threshold=similarity_threshold,
                time_range_in_days=filters.time_range_in_days,
                project_id=filters.project_id,
                topics=filters.topics,
                subtopics=filters.subtopics,
                tags=filters.tags,
                tag_values=filters.tag_values
            )
            return result
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to search events: {str(e)}") from e
        

    async def search_user_event_gists(
        self,
        user_id: str, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: Optional[str] = None
    ) -> List[UserEventGistData]:
        """
        Search user event gists by query using vector similarity.
        
        This method performs semantic search on event gist embeddings to find
        the most relevant gists matching the query.
        
        Args:
            user_id: Unique identifier for the user
            query: Text query to search for
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score 0.0-1.0 (default: 0.2)
            time_range_in_days: Number of days to look back (default: 21)
            project_id: Optional project filter. If None, searches all projects.
            
        Returns:
            List of UserEventGistData objects with similarity scores, ordered by relevance
            
        Raises:
            LindormMemobaseError: If search fails or embeddings are not enabled
            
        Example:
            # Search for relevant event gists
            gists = await memobase.search_user_event_gists(
                "user123",
                "travel destinations and plans",
                limit=8,
                similarity_threshold=0.25
            )
            
            # Search within a specific project and time window
            gists = await memobase.search_user_event_gists(
                "user123",
                "project milestones",
                project_id="work_project",
                time_range_in_days=7
            )
        """
        try:
            result = await search_user_event_gists(
                user_id=user_id,
                query=query,
                config=self.config,
                topk=limit,
                similarity_threshold=similarity_threshold,
                time_range_in_days=time_range_in_days,
                project_id=project_id
            )
            return result.gists
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to search user event gists: {str(e)}") from e
        
    
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
            conversation: List of chat messages to analyze for relevance
            topics: Optional list of topics to consider (filters profiles by topic)
            max_profiles: Maximum number of relevant profiles to return (default: 10)
            max_profile_token_size: Maximum token size for profile content (default: 4000)
            max_subtopic_size: Optional limit on subtopic content size
            topic_limits: Optional dictionary mapping topics to their individual limits
            full_profile_and_only_search_event: If True, returns full profiles and searches events only
            
        Returns:
            List of Profile objects ranked by relevance to the conversation
            
        Raises:
            LindormMemobaseError: If profile filtering fails
            
        Example:
            conversation = [
                OpenAICompatibleMessage(role="user", content="I want to plan my vacation"),
                OpenAICompatibleMessage(role="assistant", content="Where would you like to go?")
            ]
            profiles = await memobase.get_relevant_profiles("user123", conversation, topics=["travel"])
        """
        try:
            profile_section, raw_profiles = await get_user_profiles_data(
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
            
            return convert_profile_data_to_profiles(raw_profiles, self.config.profile_split_delimiter, topics, max_profiles)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
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
        fill_window_with_events: bool = False,
        project_id: Optional[str] = None
    ) -> str:
        """
        Generate comprehensive context for conversation including relevant profiles and events.
        
        Args:
            user_id: Unique identifier for the user
            conversation: Current conversation messages to analyze for context
            profile_config: Profile configuration to use (uses default if None)
            max_token_size: Maximum tokens for the generated context (default: 2000)
            prefer_topics: Topics to prioritize when selecting context
            time_range_in_days: Days to look back for relevant events (default: 30)
            event_similarity_threshold: Minimum similarity for event inclusion (default: 0.2)
            profile_event_ratio: Ratio of profile vs event content (default: 0.6)
            only_topics: Restrict context to only these topics
            max_subtopic_size: Maximum size per subtopic
            topic_limits: Per-topic token limits
            require_event_summary: Whether to include event summaries
            customize_context_prompt: Custom prompt for context generation
            full_profile_and_only_search_event: Use full profiles, search events only
            fill_window_with_events: Fill remaining token budget with events
            project_id: Optional project filter. If None, searches across all projects.
            
        Returns:
            Formatted context string ready for use in conversation
            
        Raises:
            LindormMemobaseError: If context generation fails
            
        Example:
            conversation = [
                OpenAICompatibleMessage(role="user", content="What should I cook tonight?")
            ]
            context = await memobase.get_conversation_context(
                "user123", 
                conversation, 
                prefer_topics=["cooking", "dietary_preferences"],
                max_token_size=1500
            )
        """
        try:
            if profile_config is None:
                profile_config = ProfileConfig.load_from_config(self.config)
                
            context_data = await get_user_context(
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
                fill_window_with_events=fill_window_with_events,
                project_id=project_id
            )
            
            return context_data.context
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
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
        
        This method creates a mock conversation with the query to leverage the existing
        profile filtering system that analyzes conversation relevance.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query text to find relevant profiles
            topics: Optional topic filter to restrict search scope
            max_results: Maximum number of results to return (default: 10)
            
        Returns:
            List of Profile objects matching the query, ranked by relevance
            
        Raises:
            LindormMemobaseError: If search fails
            
        Example:
            profiles = await memobase.search_profiles(
                "user123", 
                "favorite restaurants", 
                topics=["food", "dining"],
                max_results=5
            )
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

    async def search_profiles_by_embedding(
        self,
        user_id: str,
        query: str,
        topics: Optional[List[str]] = None,
        max_results: int = 10,
        min_score: float = 0.5,
        project_id: Optional[str] = None
    ) -> List[Profile]:
        """
        Search profiles using vector similarity (embedding-based search).
        
        This method uses embedding vectors to find profiles semantically similar
        to the query, bypassing LLM-based filtering for lower latency.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query text
            topics: Optional topic filter (OR logic)
            max_results: Maximum number of results to return (default: 10)
            min_score: Minimum similarity score threshold (default: 0.5)
            project_id: Optional project filter
            
        Returns:
            List of Profile objects matching the query, ranked by similarity
            
        Raises:
            LindormMemobaseError: If search fails
        """
        from lindormmemobase.core.search.user_profiles import search_profiles_by_embedding as _search
        
        try:
            result = await _search(
                user_id=user_id,
                query=query,
                global_config=self.config,
                topk=max_results,
                min_score=min_score,
                project_id=project_id,
                topics=topics
            )
            return convert_profile_data_to_profiles(
                result.profiles,
                self.config.profile_split_delimiter,
                topics,
                max_results
            )
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to search profiles by embedding: {str(e)}") from e

    async def search_profiles_with_rerank(
        self,
        user_id: str,
        query: str,
        topics: Optional[List[str]] = None,
        max_results: int = 10,
        combine_by_topic: bool = True,
        project_id: Optional[str] = None
    ) -> List[Profile]:
        """
        Search profiles using rerank model.
        
        This method retrieves all profiles and uses a rerank model to score
        and order them by relevance to the query.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query text
            topics: Optional topic filter
            max_results: Maximum number of results to return (default: 10)
            combine_by_topic: If True, combine profiles by topic::subtopic before reranking
            project_id: Optional project filter
            
        Returns:
            List of Profile objects matching the query, ranked by rerank score
            
        Raises:
            LindormMemobaseError: If search fails
        """
        from lindormmemobase.core.search.user_profiles import search_profiles_with_rerank as _search
        
        try:
            result = await _search(
                user_id=user_id,
                query=query,
                global_config=self.config,
                topk=max_results,
                project_id=project_id,
                topics=topics,
                combine_by_topic=combine_by_topic
            )
            return convert_profile_data_to_profiles(
                result.profiles,
                self.config.profile_split_delimiter,
                topics,
                max_results
            )
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to search profiles with rerank: {str(e)}") from e

    async def search_profiles_hybrid(
        self,
        user_id: str,
        query: str,
        topics: Optional[List[str]] = None,
        max_results: int = 10,
        embedding_candidates: int = 30,
        min_embedding_score: float = 0.3,
        project_id: Optional[str] = None
    ) -> List[Profile]:
        """
        Search profiles using embedding + rerank hybrid approach.
        
        This method first retrieves candidates using vector search, then
        reranks them using a rerank model for best results.
        
        Args:
            user_id: Unique identifier for the user
            query: Search query text
            topics: Optional topic filter
            max_results: Maximum number of final results (default: 10)
            embedding_candidates: Number of candidates to retrieve from embedding search (default: 30)
            min_embedding_score: Minimum similarity score for embedding search (default: 0.3)
            project_id: Optional project filter
            
        Returns:
            List of Profile objects matching the query, ranked by hybrid score
            
        Raises:
            LindormMemobaseError: If search fails
        """
        from lindormmemobase.core.search.user_profiles import hybrid_search_profiles as _search
        
        try:
            result = await _search(
                user_id=user_id,
                query=query,
                global_config=self.config,
                embedding_topk=embedding_candidates,
                final_topk=max_results,
                min_score=min_embedding_score,
                project_id=project_id,
                topics=topics
            )
            return convert_profile_data_to_profiles(
                result.profiles,
                self.config.profile_split_delimiter,
                topics,
                max_results
            )
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to hybrid search profiles: {str(e)}") from e

    # ===== Buffer Management Methods =====

    async def add_blob_to_buffer(
        self,
        user_id: str,
        blob: Blob,
        blob_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> str:
        """
        Add a blob to the processing buffer.
        
        This method queues a blob for processing in the buffer system. The blob will be
        processed automatically when the buffer reaches capacity or when manually flushed.
        
        Args:
            user_id: Unique identifier for the user
            blob: The data blob to add to the buffer (ChatBlob, DocBlob, etc.)
            blob_id: Optional custom ID for the blob. If None, generates a UUID.
            project_id: Optional project identifier for multi-tenancy. If None, uses default.
            
        Returns:
            The blob ID assigned to the added blob
            
        Raises:
            LindormMemobaseError: If blob insertion fails
            
        Example:
            from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage
            
            chat_blob = ChatBlob(
                messages=[OpenAICompatibleMessage(role="user", content="Hello world!")],
                type=BlobType.chat
            )
            blob_id = await memobase.add_blob_to_buffer("user123", chat_blob)
        """
        try:
            if blob_id is None:
                blob_id = str(uuid.uuid4())
                
            await insert_blob_to_buffer(
                user_id=user_id,
                blob_id=blob_id,
                blob_data=blob,
                config=self.config,
                project_id=project_id
            )
            
            return blob_id
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to add blob to buffer: {str(e)}") from e

    async def detect_buffer_full_or_not(
        self,
        user_id: str,
        blob_type: BlobType = BlobType.chat,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive buffer status information.

        Args:
            user_id: Unique identifier for the user
            blob_type: Type of blobs to check (default: BlobType.chat)
            project_id: Optional project identifier for multi-tenancy. If None, uses default.

        Returns:
            Dictionary containing:
            - is_full: Whether buffer should be flushed
            - buffer_full_ids: List of blob IDs if buffer is over capacity

        Raises:
            LindormMemobaseError: If buffer status check fails

        Example:
            status = await memobase.get_buffer_status("user123", BlobType.chat)
            print(f"Buffer has {status['capacity']} items, full: {status['is_full']}")
        """
        try:
            # Check if buffer is full
            buffer_full_ids = await detect_buffer_full_or_not(
                user_id=user_id,
                blob_type=blob_type,
                config=self.config,
                project_id=project_id
            )

            is_full = len(buffer_full_ids) > 0

            return {
                "is_full": is_full,
                "buffer_full_ids": buffer_full_ids,
                "blob_type": str(blob_type)
            }
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to get buffer status: {str(e)}") from e

    async def process_buffer(
        self,
        user_id: str,
        blob_type: BlobType = BlobType.chat,
        profile_config: Optional[ProfileConfig] = None,
        blob_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Process blobs in the buffer and extract memories.

        Profile config is resolved using the same logic as extract_memories:
        1. Explicitly provided profile_config parameter
        2. Project-specific config from database
        3. Global config from config.yaml (fallback)

        This method processes either all unprocessed blobs in the buffer or specific
        blob IDs, extracting user profiles and generating events based on the content.

        Args:
            user_id: Unique identifier for the user
            blob_type: Type of blobs to process (default: BlobType.chat)
            profile_config: Profile configuration for extraction. Uses DB or default if None.
            blob_ids: Specific blob IDs to process. If None, processes all unprocessed blobs.
            project_id: Optional project identifier for multi-tenancy. If None, uses default.

        Returns:
            Processing result data if successful, None if no blobs to process

        Raises:
            LindormMemobaseError: If buffer processing fails

        Example:
            # Process all unprocessed chat blobs
            result = await memobase.process_buffer("user123", BlobType.chat)

            # Process specific blob IDs with custom profile config
            custom_profile = ProfileConfig(language="zh")
            result = await memobase.process_buffer(
                "user123",
                BlobType.chat,
                profile_config=custom_profile,
                blob_ids=["blob-id-1", "blob-id-2"]
            )
        """
        try:
            from .utils.profile_config_resolver import resolve_profile_config

            # Resolve profile config (handles DB lookup and fallback)
            resolved_config = await resolve_profile_config(
                project_id=project_id,
                user_config=profile_config,
                topic_config_storage=self.topic_config_storage,
                main_config=self.config
            )

            if blob_ids is not None:
                # Process specific blob IDs
                result = await flush_buffer_by_ids(
                    user_id=user_id,
                    blob_type=blob_type,
                    buffer_ids=blob_ids,
                    config=self.config,
                    select_status=BufferStatus.idle,
                    profile_config=resolved_config,
                    project_id=project_id
                )
            else:
                # Process all unprocessed blobs
                result = await flush_buffer(
                    user_id=user_id,
                    blob_type=blob_type,
                    config=self.config,
                    profile_config=resolved_config,
                    project_id=project_id
                )

            return result
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to process buffer: {str(e)}") from e
    
    async def reset_all_storage(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reset all storage tables (buffer, events, user profiles).
        
        This is an administrative operation that clears data from all storage backends.
        When user_id and project_id are not specified, tables are dropped and recreated.
        Otherwise, data is deleted based on the provided filters.
        
        Args:
            user_id: Optional user ID filter. If None, resets all users.
            project_id: Optional project ID filter. If None, resets all projects.
            
        Returns:
            Dictionary containing reset statistics:
            - buffer_deleted: Number of buffer rows deleted
            - events_deleted: Number of event rows deleted
            - gists_deleted: Number of event gist rows deleted
            - profiles_deleted: Number of profile rows deleted
            - tables_recreated: Whether tables were dropped and recreated
            
        Raises:
            LindormMemobaseError: If reset operation fails
            
        Example:
            # Reset all data (drops and recreates tables)
            result = await memobase.reset_all_storage()
            
            # Reset data for specific user across all projects
            result = await memobase.reset_all_storage(user_id="user123")
            
            # Reset data for specific user and project
            result = await memobase.reset_all_storage(user_id="user123", project_id="proj1")
        """
        try:
            from .core.storage.manager import StorageManager
            LOG.info("Start resetting all storage...")
            return await StorageManager.reset_all_storage(self.config, user_id, project_id)
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to reset storage: {str(e)}") from e

    async def trigger_merge(
        self,
        user_id: str,
        topic: Optional[str] = None,
        subtopic: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> MergeOperationResult:
        """Manually trigger merge of pending profiles.

        Forces immediate merging of pending profiles for a user,
        optionally filtered by topic/subtopic/project.

        Args:
            user_id: User identifier
            topic: Optional topic filter
            subtopic: Optional subtopic filter
            project_id: Optional project identifier

        Returns:
            MergeOperationResult with merge statistics

        Raises:
            LindormMemobaseError: If merge operation fails

        Example:
            # Merge all pending profiles for a user
            result = await memobase.trigger_merge("user123")

            # Merge only specific topic
            result = await memobase.trigger_merge("user123", topic="interests")

            # Merge specific topic and subtopic
            result = await memobase.trigger_merge(
                "user123",
                topic="interests",
                subtopic="hobbies"
            )
        """
        from lindormmemobase.core.storage.manager import StorageManager
        from lindormmemobase.core.extraction.processor.merge import batch_merge_pending_profiles
        from lindormmemobase.config import TRACE_LOG
        from collections import defaultdict

        try:
            # Get pending_profiles storage
            pending_storage = StorageManager.get_pending_profiles_storage(self.config)

            # T028: Get pending entries with filters
            pending_entries = await pending_storage.get_pending_entries(
                user_id=user_id,
                topic=topic,
                subtopic=subtopic,
                project_id=project_id
            )

            # T031: Handle empty pending profiles case gracefully
            if not pending_entries:
                TRACE_LOG.info(
                    user_id,
                    f"No pending profiles found for merge trigger "
                    f"(topic={topic}, subtopic={subtopic}, project_id={project_id})",
                    project_id=project_id
                )
                return MergeOperationResult(
                    success=True,
                    merged_count=0,
                    topics_merged=[],
                    message="No pending profiles found matching the specified filters"
                )

            # T029: Group entries by (topic, subtopic) tuple
            groups = defaultdict(list)
            for entry in pending_entries:
                key = (entry['topic'], entry['subtopic'])
                groups[key].append(entry)

            # Batch merge each group
            total_merged = 0
            all_topics_merged = []
            failed_groups = []

            TRACE_LOG.info(
                user_id,
                f"Triggering manual merge: {len(groups)} groups to process, "
                f"{len(pending_entries)} total pending entries",
                project_id=project_id
            )

            for (group_topic, group_subtopic), entries in groups.items():
                try:
                    # Call batch_merge_pending_profiles for this group
                    result = await batch_merge_pending_profiles(
                        user_id=user_id,
                        topic=group_topic,
                        subtopic=group_subtopic,
                        config=self.config,
                        project_id=project_id,
                        pending_storage=pending_storage
                    )

                    if result.success:
                        total_merged += result.merged_count
                        all_topics_merged.extend(result.topics_merged)
                    else:
                        failed_groups.append(f"{group_topic}::{group_subtopic}")
                        TRACE_LOG.warning(
                            user_id,
                            f"Failed to merge group {group_topic}::{group_subtopic}: {result.message}",
                            project_id=project_id
                        )
                except Exception as e:
                    failed_groups.append(f"{group_topic}::{group_subtopic}")
                    TRACE_LOG.error(
                        user_id,
                        f"Exception merging group {group_topic}::{group_subtopic}: {str(e)}",
                        project_id=project_id
                    )

            # T030: Build MergeOperationResult return object
            success = len(failed_groups) == 0
            merged_count = total_merged

            if success:
                message = f"Successfully merged {merged_count} pending profiles across {len(all_topics_merged)} topic groups"
            else:
                message = (
                    f"Partial merge completed: {merged_count} profiles merged, "
                    f"{len(failed_groups)} groups failed: {', '.join(failed_groups)}"
                )

            TRACE_LOG.info(
                user_id,
                f"Manual merge completed: success={success}, merged={merged_count}, "
                f"topics_merged={len(all_topics_merged)}, failed={len(failed_groups)}",
                project_id=project_id
            )

            return MergeOperationResult(
                success=success,
                merged_count=merged_count,
                topics_merged=all_topics_merged,
                message=message
            )

        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to trigger merge: {str(e)}") from e