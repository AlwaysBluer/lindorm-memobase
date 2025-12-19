"""
Search layer for UserEventsGists operations.

This module provides high-level search and retrieval functions for event gists,
including both SQL-based time range queries and vector similarity searches.
"""
from typing import  Optional

from lindormmemobase.config import Config, TRACE_LOG
from lindormmemobase.models.response import UserEventGistsData, UserEventGistData
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.utils.errors import SearchError
from lindormmemobase.utils.tools import get_encoded_tokens
from lindormmemobase.core.storage.event_gists import get_lindorm_event_gists_storage, search_user_event_gists_with_embedding
from lindormmemobase.embedding import get_embedding

async def truncate_event_gists(
        events: UserEventGistsData,
        max_token_size: int | None,
) -> UserEventGistsData:
    """Truncate event gists list to fit within token budget.
    
    Args:
        events: UserEventGistsData containing list of gists
        max_token_size: Maximum total tokens allowed. If None, no truncation.
    
    Returns:
        UserEventGistsData with truncated gists list
    """
    if max_token_size is None:
        return events
    c_tokens = 0
    truncated_results = []
    for r in events.gists:
        c_tokens += len(get_encoded_tokens(r.gist_data.content))
        if c_tokens > max_token_size:
            break
        truncated_results.append(r)
    events.gists = truncated_results
    return events


async def get_user_event_gists_by_sql(
        user_id: str,
        config: Config,
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        max_token_size: Optional[int] = None
) -> UserEventGistsData:
    """Get user event gists from storage using SQL query without vector search.
    
    Args:
        user_id: User identifier
        config: Configuration object
        project_id: Optional project filter
        time_range_in_days: Number of days to look back
        limit: Maximum number of results
        max_token_size: Optional token budget for truncation
    
    Returns:
        UserEventGistsData containing list of gists
    """
    try:
        storage = get_lindorm_event_gists_storage(config)
        
        # Get gists using SQL filter
        gists_raw = await storage.get_event_gists_by_filter(
            user_id=user_id,
            project_id=project_id,
            time_range_in_days=time_range_in_days,
            limit=limit
        )
        
        # Convert to UserEventGistData models
        gists = []
        for gist_dict in gists_raw:
            gist_data = UserEventGistData(
                id=gist_dict['id'],
                gist_data=gist_dict['gist_data'],
                created_at=gist_dict['created_at'],
                updated_at=gist_dict['updated_at']
            )
            gists.append(gist_data)
        
        user_event_gists_data = UserEventGistsData(gists=gists)
        
        # Apply token truncation if specified
        if max_token_size:
            user_event_gists_data = await truncate_event_gists(user_event_gists_data, max_token_size)
        
        TRACE_LOG.info(
            user_id,
            f"Retrieved {len(user_event_gists_data.gists)} event gists for user (time_range={time_range_in_days} days)"
        )
        
        return user_event_gists_data
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to get user event gists by SQL: {str(e)}")
        raise SearchError(f"Failed to get user event gists: {str(e)}") from e


async def search_user_event_gists(
        user_id: str,
        query: str,
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: str = None,
) -> UserEventGistsData:
    """Search user event gists using vector similarity in Lindorm Search.
    
    Args:
        user_id: User identifier
        query: Text query to search for
        config: Configuration object
        topk: Maximum number of results
        similarity_threshold: Minimum similarity score (0.0-1.0)
        time_range_in_days: Number of days to look back
        project_id: Optional project filter. If None, searches across all projects.
    
    Returns:
        UserEventGistsData containing matching gists with similarity scores
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

        data = await search_user_event_gists_with_embedding(user_id, query, query_embedding,
                                                      config, topk, similarity_threshold, time_range_in_days, project_id)

        gists = data
        user_event_gists_data = UserEventGistsData(gists=gists)
        TRACE_LOG.info(
            user_id,
            f"Event Query: {query[:50]}" + ("..." if len(query) > 50 else "") + f" Found {len(gists)} results",
        )

        return user_event_gists_data
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to search user event gists: {str(e)}")
        raise SearchError(f"Failed to search user event gists: {str(e)}") from e


def pack_latest_chat(chats: list[OpenAICompatibleMessage], chat_num: int = 3) -> str:
    """Pack latest chat messages into a single string for query generation.
    
    Args:
        chats: List of chat messages
        chat_num: Number of recent messages to include
    
    Returns:
        Concatenated string of recent message contents
    """
    return "\n".join([f"{m.content}" for m in chats[-chat_num:]])


async def get_user_event_gists_data(
        user_id: str,
        chats: list[OpenAICompatibleMessage],
        event_similarity_threshold: float,
        time_range_in_days: int,
        global_config: Config,
        topk=30,
        project_id: Optional[str] = None,
) -> UserEventGistsData:
    """Retrieve user event gists data with optional vector search.
    
    This is an orchestration function that chooses between vector search
    and simple time-based retrieval based on configuration.
    
    Args:
        user_id: User identifier
        chats: Conversation messages for query generation
        event_similarity_threshold: Minimum similarity for vector search
        time_range_in_days: Number of days to look back
        global_config: Configuration object
        topk: Maximum number of results
    
    Returns:
        UserEventGistsData containing retrieved gists
    """
    if chats and global_config.enable_event_embedding:
        search_query = pack_latest_chat(chats)
        p = await search_user_event_gists(
            user_id,
            query=search_query,
            config=global_config,
            topk=topk,
            similarity_threshold=event_similarity_threshold,
            time_range_in_days=time_range_in_days,
            project_id=project_id,
        )
    else:
        p = await get_user_event_gists_by_sql(
            user_id,
            config=global_config,
            project_id=project_id,
            time_range_in_days=time_range_in_days,
            limit=topk,
        )
    return p
