from pydantic import ValidationError

from ....config import TRACE_LOG, Config

from ....models.types import MergeAddResult
from ....models.response import IdsData, EventData, CODE
from ....embedding import get_embedding

from ....models.promise import Promise
from ....utils.tools import event_embedding_str

from ....core.storage.events import store_event_with_embedding, store_event_gist_with_embedding
from ....core.storage.user_profiles import add_user_profiles, update_user_profiles, delete_user_profiles

async def handle_session_event(
    user_id: str,
    memo_str: str,
    delta_profile_data: list[dict],
    event_tags: list | None,
    config: Config,
) -> Promise[str]:
    # Skip event handling if event embedding is disabled
    if not config.enable_event_embedding:
        return Promise.resolve("mock_event_id")

    eid = await append_user_event(
        user_id,
        {
            "event_tip": memo_str,
            "event_tags": event_tags,
            "profile_delta": delta_profile_data,
        },
        config=config,
    )

    return eid


async def handle_user_profile_db(
    user_id: str, intermediate_profile: MergeAddResult, config: Config
) -> Promise[IdsData]:
    TRACE_LOG.info(
        user_id,
        f"Adding {len(intermediate_profile['add'])}, updating {len(intermediate_profile['update'])}, deleting {len(intermediate_profile['delete'])} profiles",
    )

    p = await add_update_delete_user_profiles(
        user_id,
        [ap["content"] for ap in intermediate_profile["add"]],
        [ap["attributes"] for ap in intermediate_profile["add"]],
        [up["profile_id"] for up in intermediate_profile["update"]],
        [up["content"] for up in intermediate_profile["update"]],
        [up["attributes"] for up in intermediate_profile["update"]],
        intermediate_profile["delete"],
        config=config,
    )
    return p

async def append_user_event(
    user_id: str, event_data: dict, config: Config
) -> Promise[str]:
    try:
        validated_event = EventData(**event_data)
    except ValidationError as e:
        TRACE_LOG.error(
            user_id,
            f"Invalid event data: {str(e)}",
        )
        return Promise.reject(
            CODE.INTERNAL_SERVER_ERROR,
            f"Invalid event data: {str(e)}",
        )

    if config.enable_event_embedding:
        event_data_str = event_embedding_str(validated_event)
        embedding = await get_embedding(
            [event_data_str],
            phase="document",
            model=config.embedding_model,
            config=config,
        )
        if not embedding.ok():
            TRACE_LOG.error(
                user_id,
                f"Failed to get embeddings: {embedding.msg()}",
            )
            embedding = [None]
        else:
            embedding = embedding.data()
            embedding_dim_current = embedding.shape[-1]
            if embedding_dim_current != config.embedding_dim:
                TRACE_LOG.error(
                    user_id,
                    f"Embedding dimension mismatch! Expected {config.embedding_dim}, got {embedding_dim_current}.",
                )
                embedding = [None]
    else:
        embedding = [None]

    event_result = await store_event_with_embedding(
        user_id, 
        validated_event.model_dump(), 
        embedding[0],
        config=config,
    )
    
    if not event_result.ok():
        return event_result
    
    event_id = event_result.data()

    if validated_event.event_tip is not None:
        event_gists = validated_event.event_tip.split("\n")
        event_gists = [l.strip() for l in event_gists if l.strip().startswith("-")]
        TRACE_LOG.info(
            user_id, f"Processing {len(event_gists)} event gists"
        )
        
        if config.enable_event_embedding:
            event_gists_embedding = await get_embedding(
                event_gists,
                phase="document",
                model=config.embedding_model,
                config=config,
            )
            if not event_gists_embedding.ok():
                TRACE_LOG.error(
                    user_id,
                    f"Failed to get embeddings: {event_gists_embedding.msg()}",
                )
                event_gists_embedding = [None] * len(event_gists)
            else:
                event_gists_embedding = event_gists_embedding.data()
        else:
            event_gists_embedding = [None] * len(event_gists)

        for event_gist, event_gist_embedding in zip(event_gists, event_gists_embedding):
            gist_result = await store_event_gist_with_embedding(
                user_id,
                event_id,
                {"content": event_gist},
                event_gist_embedding,
                config=config,
            )
            if not gist_result.ok():
                TRACE_LOG.error(user_id, f"Failed to store gist: {gist_result.msg()}")

    return Promise.resolve(event_id)

    
async def add_update_delete_user_profiles(
    user_id: str,
    add_profiles: list[str],
    add_attributes: list[dict],
    update_profile_ids: list[str],
    update_contents: list[str],
    update_attributes: list[dict | None],
    delete_profile_ids: list[str],
    config: Config,
) -> Promise[IdsData]:
    assert len(add_profiles) == len(
        add_attributes
    ), "Length of add_profiles, add_attributes must be equal"
    assert len(update_profile_ids) == len(
        update_contents
    ), "Length of update_profile_ids, update_contents must be equal"
    assert len(update_profile_ids) == len(
        update_attributes
    ), "Length of update_profile_ids, update_attributes must be equal"

    try:
        add_profile_ids = []
        
        if len(add_profiles):
            add_result = await add_user_profiles(
                user_id, add_profiles, add_attributes, config
            )
            if not add_result.ok():
                return add_result
            add_profile_ids = add_result.data()

        if len(update_profile_ids):
            update_result = await update_user_profiles(
                user_id, update_profile_ids, update_contents, update_attributes, config
            )
            if not update_result.ok():
                return update_result

        if len(delete_profile_ids):
            delete_result = await delete_user_profiles(
                user_id, delete_profile_ids, config
            )
            if not delete_result.ok():
                return delete_result

        return Promise.resolve(IdsData(ids=add_profile_ids))
        
    except Exception as e:
        TRACE_LOG.error(
            user_id,
            f"Error merging user profiles: {e}",
        )
        return Promise.reject(
            CODE.SERVER_PARSE_ERROR, f"Error merging user profiles: {e}"
        )