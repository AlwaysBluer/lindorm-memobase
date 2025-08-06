from config import Config, TRACE_LOG

from models.response import UserEventGistsData, CODE
from models.blob import OpenAICompatibleMessage

from utils.promise import Promise

from utils.tools import get_encoded_tokens

def pack_latest_chat(chats: list[OpenAICompatibleMessage], chat_num: int = 3) -> str:
    return "\n".join([f"{m.content}" for m in chats[-chat_num:]])

async def truncate_event_gists(
    events: UserEventGistsData,
    max_token_size: int | None,
) -> Promise[UserEventGistsData]:
    if max_token_size is None:
        return Promise.resolve(events)
    c_tokens = 0
    truncated_results = []
    for r in events.gists:
        c_tokens += len(get_encoded_tokens(r.gist_data.content))
        if c_tokens > max_token_size:
            break
        truncated_results.append(r)
    events.gists = truncated_results
    return Promise.resolve(events)



async def get_user_event_gists_data(
    user_id: str,
    chats: list[OpenAICompatibleMessage],
    require_event_summary: bool,
    event_similarity_threshold: float,
    time_range_in_days: int,
    global_config: Config
) -> Promise[UserEventGistsData]:
    """Retrieve user events data."""
    if chats and global_config.enable_event_embedding:
        search_query = pack_latest_chat(chats)
        p = await search_user_event_gists(
            user_id,
            query=search_query,
            topk=60,
            similarity_threshold=event_similarity_threshold,
            time_range_in_days=time_range_in_days,
        )
    else:
        p = await get_user_event_gists(
            user_id,
            topk=60,
            time_range_in_days=time_range_in_days,
        )
    return p

async def get_user_event_gists(
    user_id: str,
    topk: int = 10,
    time_range_in_days: int = 21,
) -> Promise[UserEventGistsData]:
    with Session() as session:
        query = (
            session.query(UserEventGist)
            .filter_by(user_id=user_id, project_id=project_id)
            .filter(
                UserEventGist.created_at
                > (func.now() - timedelta(days=time_range_in_days))
            )
        )
        user_event_gists = (
            query.order_by(UserEventGist.created_at.desc()).limit(topk).all()
        )
        if user_event_gists is None:
            return Promise.resolve(UserEventGistsData(gists=[]))
        results = [
            {
                "id": ue.id,
                "gist_data": ue.gist_data,
                "created_at": ue.created_at,
                "updated_at": ue.updated_at,
            }
            for ue in user_event_gists
        ]
    gists = UserEventGistsData(gists=results)
    return Promise.resolve(gists)


async def search_user_event_gists(
    user_id: str,
    query: str,
    global_config: Config,
    topk: int = 10,
    similarity_threshold: float = 0.2,
    time_range_in_days: int = 21,
) -> Promise[UserEventGistsData]:
    if not global_config.enable_event_embedding:
        TRACE_LOG.warning(
            user_id,
            "Event embedding is not enabled, skip search",
        )
        return Promise.reject(
            CODE.NOT_IMPLEMENTED,
            "Event embedding is not enabled",
        )
    query_embeddings = await get_embedding(
        [query], phase="query", model=global_config.embedding_model
    )
    if not query_embeddings.ok():
        TRACE_LOG.error(
            user_id,
            f"Failed to get embeddings: {query_embeddings.msg()}",
        )
        return query_embeddings
    query_embedding = query_embeddings.data()[0]

    # Calculate the time cutoff once
    time_cutoff = func.now() - timedelta(days=time_range_in_days)

    # Store the similarity expression to avoid recomputation
    similarity_expr = 1 - UserEventGist.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            UserEventGist,
            similarity_expr.label("similarity"),
        )
        .where(
            UserEventGist.user_id == user_id,
            UserEventGist.project_id == project_id,
            UserEventGist.created_at > time_cutoff,
            similarity_expr > similarity_threshold,
            UserEventGist.embedding.is_not(None),  # Skip null embeddings
        )
        .order_by(desc("similarity"))
        .limit(topk)
    )

    with Session() as session:
        # Use .all() instead of .scalars().all() to get both columns
        result = session.execute(stmt).all()
        user_event_gists: list[UserEventGistData] = []
        for row in result:
            user_event: UserEventGist = row[0]  # UserEventGist object
            similarity: float = row[1]  # similarity value
            user_event_gists.append(
                UserEventGistData(
                    id=user_event.id,
                    gist_data=user_event.gist_data,
                    created_at=user_event.created_at,
                    updated_at=user_event.updated_at,
                    similarity=similarity,
                )
            )

        # Create UserEventsData with the events
        user_event_gists_data = UserEventGistsData(gists=user_event_gists)
        TRACE_LOG.info(
            project_id,
            user_id,
            f"Event Query: {query}",
        )

    return Promise.resolve(user_event_gists_data)