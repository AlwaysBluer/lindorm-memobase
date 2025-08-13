#!/usr/bin/env python3
"""
LindormMemobase - User-configurable memory extraction system

This module provides the main entry points for users to interact with
the memory extraction system using their own configuration.
"""

import os
import yaml
import uuid
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from .config import Config
from .models.profile_topic import ProfileConfig
from .models.blob import Blob, BlobType, OpenAICompatibleMessage
from .models.types import  Profile, ProfileEntry
from .core.extraction.processor.process_blobs import process_blobs
from .core.search.context import get_user_context
from .core.search.events import get_user_event_gists, search_user_event_gists
from .core.search.user_profiles import get_user_profiles_data, filter_profiles_with_chats
from .core.storage.user_profiles import get_user_profiles
from .core.buffer.buffer import (
    get_lindorm_buffer_storage, 
    get_buffer_capacity, 
    insert_blob_to_buffer,
    detect_buffer_full_or_not,
    get_unprocessed_buffer_ids,
    flush_buffer_by_ids,
    flush_buffer
)
from .core.constants import BufferStatus


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
            # Load configuration using Config.from_yaml_file approach
            config_dict = {}
            config_dict.update(kwargs)
            
            # Create Config with all fields from kwargs, filling in missing values from Config defaults
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
            topics: Optional list of topics to filter by. If provided, only profiles 
                   with matching topics will be returned.
            
        Returns:
            List of user profiles grouped by topic and subtopic
            
        Raises:
            LindormMemobaseError: If profile retrieval fails
            
        Example:
            profiles = await memobase.get_user_profiles("user123", topics=["interests", "preferences"])
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
            time_range_in_days: Number of days to look back for events (default: 21)
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List of event dictionaries containing id, content, created_at, updated_at
            
        Raises:
            LindormMemobaseError: If event retrieval fails
            
        Example:
            events = await memobase.get_events("user123", time_range_in_days=30, limit=50)
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
            query: Search query string to find relevant events
            limit: Maximum number of results to return (default: 10)
            similarity_threshold: Minimum similarity score (0.0-1.0, default: 0.2)
            time_range_in_days: Number of days to look back (default: 21)
            
        Returns:
            List of event dictionaries with similarity scores, sorted by relevance
            
        Raises:
            LindormMemobaseError: If search fails
            
        Example:
            events = await memobase.search_events("user123", "travel plans", limit=5, similarity_threshold=0.3)
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
                    "id": str(gist.id),
                    "content": gist.gist_data.content if gist.gist_data else "",
                    "created_at": gist.created_at.isoformat() if gist.created_at else None,
                    "updated_at": gist.updated_at.isoformat() if gist.updated_at else None,
                    "similarity": gist.similarity if gist.similarity is not None else 0.0
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

    # ===== Buffer Management Methods =====

    async def add_blob_to_buffer(
        self,
        user_id: str,
        blob: Blob,
        blob_id: Optional[str] = None
    ) -> str:
        """
        Add a blob to the processing buffer.
        
        This method queues a blob for processing in the buffer system. The blob will be
        processed automatically when the buffer reaches capacity or when manually flushed.
        
        Args:
            user_id: Unique identifier for the user
            blob: The data blob to add to the buffer (ChatBlob, DocBlob, etc.)
            blob_id: Optional custom ID for the blob. If None, generates a UUID.
            
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
                
            result = await insert_blob_to_buffer(
                user_id=user_id,
                blob_id=blob_id,
                blob_data=blob,
                config=self.config
            )
            
            if not result.ok():
                raise LindormMemobaseError(f"Failed to add blob to buffer: {result.msg()}")
                
            return blob_id
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to add blob to buffer: {str(e)}") from e

    async def detect_buffer_full_or_not(
        self,
        user_id: str,
        blob_type: BlobType = BlobType.chat
    ) -> Dict[str, Any]:
        """
        Get comprehensive buffer status information.

        Args:
            user_id: Unique identifier for the user
            blob_type: Type of blobs to check (default: BlobType.chat)

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
            full_result = await detect_buffer_full_or_not(
                user_id=user_id,
                blob_type=blob_type,
                config=self.config
            )

            if not full_result.ok():
                raise LindormMemobaseError(f"Failed to detect buffer full status: {full_result.msg()}")

            buffer_full_ids = full_result.data()
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
        blob_ids: Optional[List[str]] = None
    ) -> Optional[Any]:
        """
        Process blobs in the buffer and extract memories.
        
        This method processes either all unprocessed blobs in the buffer or specific
        blob IDs, extracting user profiles and generating events based on the content.
        
        Args:
            user_id: Unique identifier for the user
            blob_type: Type of blobs to process (default: BlobType.chat)
            profile_config: Profile configuration for extraction. Uses default if None.
            blob_ids: Specific blob IDs to process. If None, processes all unprocessed blobs.
            
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
            if profile_config is None:
                profile_config = ProfileConfig()
                
            if blob_ids is not None:
                # Process specific blob IDs
                result = await flush_buffer_by_ids(
                    user_id=user_id,
                    blob_type=blob_type,
                    buffer_ids=blob_ids,
                    config=self.config,
                    select_status=BufferStatus.idle,
                    profile_config=profile_config
                )
            else:
                # Process all unprocessed blobs
                result = await flush_buffer(
                    user_id=user_id,
                    blob_type=blob_type,
                    config=self.config,
                    profile_config=profile_config
                )
                
            if not result.ok():
                raise LindormMemobaseError(f"Buffer processing failed: {result.msg()}")
                
            return result.data()
        except Exception as e:
            if isinstance(e, LindormMemobaseError):
                raise
            raise LindormMemobaseError(f"Failed to process buffer: {str(e)}") from e