from typing import List

from ...config import Config, TRACE_LOG
from ...models.response import UserEventGistsData, UserEventData
from ...models.blob import OpenAICompatibleMessage
from ...utils.errors import SearchError
from ...utils.tools import get_encoded_tokens
from ..storage.events import get_lindorm_search_storage, search_user_event_gists_with_embedding, \
    search_user_events_with_embedding
from ...embedding import get_embedding
from datetime import datetime, timedelta, timezone


def pack_latest_chat(chats: list[OpenAICompatibleMessage], chat_num: int = 3) -> str:
    return "\n".join([f"{m.content}" for m in chats[-chat_num:]])


async def truncate_event_gists(
        events: UserEventGistsData,
        max_token_size: int | None,
) -> UserEventGistsData:
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


async def get_user_event_gists_data(
        user_id: str,
        chats: list[OpenAICompatibleMessage],
        require_event_summary: bool,
        event_similarity_threshold: float,
        time_range_in_days: int,
        global_config: Config,
        topk=60
) -> UserEventGistsData:
    """Retrieve user events data."""
    if chats and global_config.enable_event_embedding:
        search_query = pack_latest_chat(chats)
        p = await search_user_event_gists(
            user_id,
            query=search_query,
            config=global_config,
            topk=topk,
            similarity_threshold=event_similarity_threshold,
            time_range_in_days=time_range_in_days,
        )
    else:
        p = await get_user_event_gists(
            user_id,
            config=global_config,
            topk=topk,
            time_range_in_days=time_range_in_days,
        )
    return p


async def get_user_event_gists(
        user_id: str,
        config: Config,
        topk: int = 10,
        time_range_in_days: int = 21,
) -> UserEventGistsData:
    """Get user event gists from Lindorm Search without vector search."""
    try:
        storage = get_lindorm_search_storage(config)

        # Calculate time cutoff
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)

        # Search query to get recent gists for the user
        query = {
            "size": topk,
            "sort": [{"created_at": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": user_id}},
                        {"range": {"created_at": {"gte": time_cutoff.isoformat()}}}
                    ]
                }
            }
        }

        response = storage.client.search(
            index=config.lindorm_search_event_gists_index,
            body=query,
            routing=user_id
        )

        # Debug logging to understand response structure
        if not response or 'hits' not in response or 'hits' not in response['hits']:
            TRACE_LOG.error(user_id, f"Invalid search response structure: {response}")
            return UserEventGistsData(gists=[])

        gists = []
        for hit in response['hits']['hits']:
            if '_source' not in hit:
                TRACE_LOG.error(user_id, f"Missing _source in search hit: {hit.keys()}")
                continue
            source = hit['_source']
            # Check if required fields exist in source
            if 'gist_data' not in source or 'created_at' not in source:
                TRACE_LOG.error(user_id, f"Missing required fields in _source: {source.keys()}")
                continue
            gists.append({
                "id": hit['_id'],
                "gist_data": source['gist_data'],
                "created_at": source['created_at'],
                "updated_at": source.get('updated_at', source['created_at'])
            })

        return UserEventGistsData(gists=gists)
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to get user event gists: {str(e)}")
        raise SearchError(f"Failed to get user event gists: {str(e)}") from e


async def search_user_event_gists(
        user_id: str,
        query: str,
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
) -> UserEventGistsData:
    """Search user event gists using vector similarity in Lindorm Search."""
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
                                                      config, topk, similarity_threshold, time_range_in_days)

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


async def search_user_event(
        user_id: str,
        query: str,
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
) -> List[UserEventData]:
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

        data = await search_user_events_with_embedding(user_id, query, query_embedding,
                                                 config, topk, similarity_threshold, time_range_in_days)

        responses = data
        results = []
        for resp in responses:
            user_event_gists_data = UserEventData(
                id=resp['id'],
                event_data=resp['event_data'],
                created_at=resp['created_at'],
                updated_at=resp.get('updated_at', resp['created_at']),
                similarity=resp['similarity']
            )
            results.append(user_event_gists_data)
        TRACE_LOG.info(
            user_id,
            f"Event Query: {query[:50]}" + ("..." if len(query) > 50 else "") + f" Found {len(responses)} results",
        )

        return results

    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to search user event gists: {str(e)}")
        raise SearchError(f"Failed to search user event gists: {str(e)}") from e
