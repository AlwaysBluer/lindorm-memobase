import asyncio
import uuid
from pydantic import ValidationError

from ....config import TRACE_LOG, Config

from ....models.types import MergeAddResult
from ....models.response import IdsData, EventData, CODE, EventGistWithAction
from ....embedding import get_embedding

from ....models.promise import Promise
from ....utils.tools import event_embedding_str

from ....core.storage.events import store_event_with_embedding, store_event_gist_with_embedding, \
    update_event_gist_with_embedding, delete_event, delete_event_gists_by_event_id, delete_event_gist
from ....core.storage.user_profiles import add_user_profiles, update_user_profiles, delete_user_profiles


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


async def handle_session_event(
        user_id: str,
        event_id: str,
        memo_str: str,
        delta_profile_data: list[dict],
        event_tags: list | None,
        config: Config,
) -> Promise[str]:
    eid = await append_user_event(
        user_id,
        event_id,
        {
            "event_tip": memo_str,
            "event_tags": event_tags,
            "profile_delta": delta_profile_data,
        },
        config
    )
    if not eid.ok():
        return Promise.reject(eid.code(), eid.msg())
    eid = eid.data()
    return Promise.resolve(eid)


async def handle_session_event_gists(
        user_id: str,
        event_id: str,
        event_gists_with_actions: list[EventGistWithAction],
        config: Config,
) -> Promise[None]:
    """
    并发处理所有 event gist 操作
    """
    if not config.enable_event_embedding:
        return Promise.resolve(None)

    if not event_gists_with_actions:
        return Promise.resolve(None)

    tasks = []
    for event in event_gists_with_actions:
        if event.action == "ADD":
            tasks.append(
                store_event_gist_with_embedding(
                    user_id,
                    event_id,
                    {"content": event.text},
                    event.embedding,
                    config,
                )
            )
        elif event.action == "UPDATE":
            tasks.append(
                update_event_gist_with_embedding(
                    user_id,
                    event.event_gist_id,
                    {"content": event.text},
                    event.embedding,
                    config,
                )
            )
        elif event.action == "DELETE":
            tasks.append(
                delete_event_gist(
                    user_id,
                    event.event_gist_id,
                    config
                )
            )
        elif event.action == "ABORT":
            continue

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"Task {idx} failed: {str(result)}")
                TRACE_LOG.error(user_id, f"Event gist operation failed: {str(result)}")
            elif hasattr(result, 'ok') and not result.ok():
                errors.append(f"Task {idx} failed: {result.msg()}")
                TRACE_LOG.error(user_id, f"Event gist operation failed: {result.msg()}")

        if errors:
            return Promise.reject(
                CODE.SERVER_PROCESS_ERROR,
                f"Failed to process event gists: {'; '.join(errors)}"
            )

    return Promise.resolve(None)


async def append_user_event(
        user_id: str, event_id: str, event_data: dict, config: Config
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
        event_id,
        validated_event.model_dump(),
        embedding[0],
        config=config,
    )

    if not event_result.ok():
        return event_result

    event_id = event_result.data()
    return Promise.resolve(event_id)
