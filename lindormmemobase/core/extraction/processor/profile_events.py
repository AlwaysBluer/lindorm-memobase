import asyncio
import uuid
from pydantic import ValidationError

from ....config import TRACE_LOG, Config

from ....models.types import MergeAddResult
from ....models.response import IdsData, EventData, EventGistWithAction
from ....embedding import get_embedding
from ....utils.errors import StorageError

from ....utils.tools import event_embedding_str

from ....core.storage.events import store_event_with_embedding, store_event_gist_with_embedding, \
    update_event_gist_with_embedding, delete_event, delete_event_gists_by_event_id, delete_event_gist
from ....core.storage.user_profiles import add_user_profiles, update_user_profiles, delete_user_profiles


def split_concatenated_profiles(
    add_profiles: list[dict],
    update_profiles: list[dict],
    delete_profile_ids: list[str]
) -> tuple[list[dict], list[dict], list[str]]:
    """
    Split profiles containing ;; markers into individual profiles.
    
    For ADD list: Split content by ;; into multiple profiles
    For UPDATE list: If content contains ;;, move to DELETE list and create new ADD entries
    
    Returns:
        Tuple of (expanded_add_list, cleaned_update_list, expanded_delete_list)
    """
    expanded_add = []
    cleaned_update = []
    expanded_delete = list(delete_profile_ids)
    
    # Process ADD list - split concatenated content
    for profile in add_profiles:
        content = profile["content"]
        attributes = profile["attributes"]
        
        if ";;" in content:
            # Split by ;; and create separate profiles
            split_contents = [c.strip() for c in content.split(";;") if c.strip()]
            for split_content in split_contents:
                expanded_add.append({
                    "content": split_content,
                    "attributes": attributes.copy()
                })
        else:
            # Keep as single profile
            expanded_add.append(profile)
    
    # Process UPDATE list - convert concatenated updates to DELETE + ADD
    for profile in update_profiles:
        content = profile["content"]
        profile_id = profile["profile_id"]
        attributes = profile["attributes"]
        
        if ";;" in content:
            # Mark old profile for deletion
            expanded_delete.append(profile_id)
            
            # Split content and create new profiles
            split_contents = [c.strip() for c in content.split(";;") if c.strip()]
            for split_content in split_contents:
                expanded_add.append({
                    "content": split_content,
                    "attributes": attributes.copy()
                })
        else:
            # Keep as normal update
            cleaned_update.append(profile)
    
    return expanded_add, cleaned_update, expanded_delete


async def handle_user_profile_db(
        user_id: str, intermediate_profile: MergeAddResult, config: Config, project_id: str | None = None
) -> IdsData:
    # Split concatenated profiles before storage
    add_list = [
        {"content": ap["content"], "attributes": ap["attributes"]}
        for ap in intermediate_profile["add"]
    ]
    update_list = [
        {"profile_id": up["profile_id"], "content": up["content"], "attributes": up["attributes"]}
        for up in intermediate_profile["update"]
    ]
    delete_list = list(intermediate_profile["delete"])
    
    # Apply splitting logic
    expanded_add, cleaned_update, expanded_delete = split_concatenated_profiles(
        add_list, update_list, delete_list
    )
    
    TRACE_LOG.info(
        user_id,
        f"After splitting: Adding {len(expanded_add)}, updating {len(cleaned_update)}, deleting {len(expanded_delete)} profiles",
    )

    p = await add_update_delete_user_profiles(
        user_id,
        [ap["content"] for ap in expanded_add],
        [ap["attributes"] for ap in expanded_add],
        [up["profile_id"] for up in cleaned_update],
        [up["content"] for up in cleaned_update],
        [up["attributes"] for up in cleaned_update],
        expanded_delete,
        config=config,
        project_id=project_id,
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
        project_id: str | None = None,
) -> IdsData:
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
            add_profile_ids = await add_user_profiles(
                user_id, add_profiles, add_attributes, config, project_id=project_id
            )

        if len(update_profile_ids):
            await update_user_profiles(
                user_id, update_profile_ids, update_contents, update_attributes, config, project_id=project_id
            )

        if len(delete_profile_ids):
            await delete_user_profiles(
                user_id, delete_profile_ids, config, project_id=project_id
            )

        return IdsData(ids=add_profile_ids)

    except Exception as e:
        TRACE_LOG.error(
            user_id,
            f"Error merging user profiles: {e}",
        )
        raise StorageError(f"Error merging user profiles: {e}") from e


async def handle_session_event(
        user_id: str,
        event_id: str,
        memo_str: str,
        delta_profile_data: list[dict],
        event_tags: list | None,
        config: Config,
) -> str:
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
    return eid


async def handle_session_event_gists(
        user_id: str,
        event_id: str,
        event_gists_with_actions: list[EventGistWithAction],
        config: Config,
) -> None:
    """
    并发处理所有 event gist 操作
    """
    if not config.enable_event_embedding:
        return

    if not event_gists_with_actions:
        return

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

        if errors:
            raise StorageError(f"Failed to process event gists: {'; '.join(errors)}")


async def append_user_event(
        user_id: str, event_id: str, event_data: dict, config: Config
) -> str:
    try:
        validated_event = EventData(**event_data)
    except ValidationError as e:
        TRACE_LOG.error(
            user_id,
            f"Invalid event data: {str(e)}",
        )
        raise StorageError(f"Invalid event data: {str(e)}") from e

    if config.enable_event_embedding:
        event_data_str = event_embedding_str(validated_event)
        try:
            embedding = await get_embedding(
                [event_data_str],
                phase="document",
                model=config.embedding_model,
                config=config,
            )
            embedding_dim_current = embedding.shape[-1]
            if embedding_dim_current != config.embedding_dim:
                TRACE_LOG.error(
                    user_id,
                    f"Embedding dimension mismatch! Expected {config.embedding_dim}, got {embedding_dim_current}.",
                )
                embedding = [None]
        except Exception as e:
            TRACE_LOG.error(
                user_id,
                f"Failed to get embeddings: {str(e)}",
            )
            embedding = [None]
    else:
        embedding = [None]

    event_id = await store_event_with_embedding(
        user_id,
        event_id,
        validated_event.model_dump(),
        embedding[0],
        config=config,
    )

    return event_id
