"""Search layer for UserEvents operations.

This module provides high-level search and retrieval functions for full events,
including both SQL-based time range queries and vector similarity searches.
"""
from typing import List, Optional

from lindormmemobase.config import Config, TRACE_LOG
from lindormmemobase.models.response import UserEventData
from lindormmemobase.utils.errors import SearchError
from lindormmemobase.utils.tools import get_encoded_tokens
from lindormmemobase.core.storage.events import get_events_by_filter, search_user_events_with_embedding
from lindormmemobase.embedding import get_embedding


async def get_user_events(
        user_id: str,
        config: Config,
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        max_token_size: Optional[int] = None
) -> List[UserEventData]:
    """Get user events from storage using SQL query without vector search.
    
    Args:
        user_id: User identifier
        config: Configuration object
        project_id: Optional project filter
        time_range_in_days: Number of days to look back
        limit: Maximum number of results
        max_token_size: Optional token budget for truncation
    
    Returns:
        List of UserEventData objects
    """
    try:
        # Get events using SQL filter from storage layer
        events_raw = await get_events_by_filter(
            user_id=user_id,
            project_id=project_id,
            time_range_in_days=time_range_in_days,
            limit=limit,
            config=config
        )
        
        # Convert to UserEventData models
        results = []
        total_tokens = 0
        
        for event_dict in events_raw:
            event_data = UserEventData(
                id=event_dict['id'],
                event_data=event_dict['event_data'],
                created_at=event_dict['created_at'],
                updated_at=event_dict['updated_at']
            )
            
            # Apply token budget if specified
            if max_token_size:
                # Estimate tokens for this event
                event_text = str(event_dict['event_data'])
                event_tokens = len(get_encoded_tokens(event_text))
                
                if total_tokens + event_tokens > max_token_size:
                    break
                    
                total_tokens += event_tokens
            
            results.append(event_data)
        
        TRACE_LOG.info(
            user_id,
            f"Retrieved {len(results)} events for user (time_range={time_range_in_days} days)"
        )
        
        return results
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to get user events: {str(e)}")
        raise SearchError(f"Failed to get user events: {str(e)}") from e


async def search_user_events(
        user_id: str,
        query: str,
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: str = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        tag_values: Optional[List[str]] = None
) -> List[UserEventData]:
    """Search user events using vector similarity with advanced filters.
    
    Args:
        user_id: User identifier
        query: Text query to search for
        config: Configuration object
        topk: Maximum number of results
        similarity_threshold: Minimum similarity score (0.0-1.0)
        time_range_in_days: Number of days to look back
        project_id: Optional project filter. If None, searches across all projects.
        topics: Filter by event_data.profile_delta.attributes.topic (OR logic)
        subtopics: Filter by event_data.profile_delta.attributes.sub_topic (OR logic)
        tags: Filter by event_data.event_tags.tag (OR logic)
        tag_values: Filter by event_data.event_tags.value (OR logic)
    
    Returns:
        List of UserEventData objects with similarity scores
    """
    if not config.enable_event_embedding:
        TRACE_LOG.warning(
            user_id,
            "Event embedding is not enabled, skip search",
        )
        raise SearchError("Event embedding is not enabled")
    try:
        query_embeddings = await get_embedding(
            [query], phase="query", model=config.embedding_model, config=config
        )
        query_embedding = query_embeddings[0]
        # Convert ndarray to list if necessary
        if hasattr(query_embedding, 'tolist'):
            query_embedding = query_embedding.tolist()

        data = await search_user_events_with_embedding(
            user_id, query, query_embedding,
            config, topk, similarity_threshold, time_range_in_days, project_id,
            topics=topics,
            subtopics=subtopics,
            tags=tags,
            tag_values=tag_values
        )

        responses = data
        results = []
        for resp in responses:
            user_event_data = UserEventData(
                id=resp['id'],
                event_data=resp['event_data'],
                created_at=resp['created_at'],
                updated_at=resp.get('updated_at', resp['created_at']),
                similarity=resp['similarity']
            )
            results.append(user_event_data)
        # Build filter summary for logging
        filter_parts = []
        if topics:
            filter_parts.append(f"topics={topics}")
        if subtopics:
            filter_parts.append(f"subtopics={subtopics}")
        if tags:
            filter_parts.append(f"tags={tags}")
        if tag_values:
            filter_parts.append(f"tag_values={tag_values}")
        
        filter_summary = f" ({', '.join(filter_parts)})" if filter_parts else ""
        
        TRACE_LOG.info(
            user_id,
            f"Event Query: {query[:50]}" + ("..." if len(query) > 50 else "") + 
            f" Found {len(responses)} results" + filter_summary,
        )

        return results

    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to search user events: {str(e)}")
        raise SearchError(f"Failed to search user events: {str(e)}") from e




