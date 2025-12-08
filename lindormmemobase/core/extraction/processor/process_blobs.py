import asyncio
import uuid

import numpy

from ....embedding import get_embedding
from ....utils.tools import get_blob_str, get_encoded_tokens
from ....utils.errors import ExtractionError

from ....config import Config, TRACE_LOG
from ....models.blob import Blob
from ....models.response import ChatModalResponse, EventProcessResult, EventGist
from ....models.types import MergeAddResult
from ....models.profile_topic import ProfileConfig

from .extract import extract_topics
from .merge import merge_or_valid_new_profile, handle_merge_or_validate_new_event_gists
from .organize import organize_profiles
from .event_summary import tag_event
from .entry_summary import entry_chat_summary
from .summary import re_summary
from .profile_events import handle_session_event, handle_user_profile_db, handle_session_event_gists


def truncate_chat_blobs(
        blobs: list[Blob], max_token_size: int
) -> [list[Blob]]:
    results = []
    total_token_size = 0
    for b in blobs[::-1]:
        ts = len(get_encoded_tokens(get_blob_str(b)))
        total_token_size += ts
        if total_token_size <= max_token_size:
            results.append(b)
        else:
            break
    return results[::-1]


async def process_blobs(
        user_id: str, profile_config: ProfileConfig, blobs: list[Blob], config: Config, project_id: str | None = None
) -> ChatModalResponse:
    # 1. Extract patch profiles
    blobs = truncate_chat_blobs(blobs, config.max_chat_blob_buffer_process_token_size)
    if len(blobs) == 0:
        raise ExtractionError("No blobs to process after truncating")

    user_memo_str = await entry_chat_summary(blobs, profile_config, config)

    event_gists_texts = user_memo_str.split("\n")
    event_gists_texts = [l.strip() for l in event_gists_texts if l.strip().startswith("-")]
    TRACE_LOG.info(user_id, f"Processing {len(event_gists_texts)} event gists")
    if config.enable_event_embedding and len(event_gists_texts) > 0:
        try:
            event_gists_embeddings = await get_embedding(
                event_gists_texts,
                phase="document",
                model=config.embedding_model,
                config=config,
            )
        except Exception as e:
            TRACE_LOG.error(user_id, f"Failed to get embeddings: {str(e)}")
            event_gists_embeddings = [None] * len(event_gists_texts)
    else:
        event_gists_embeddings = [None] * len(event_gists_texts)

    event_gists = [
        EventGist(text=text, embedding=emb)
        for text, emb in zip(event_gists_texts, event_gists_embeddings)
    ]

    processing_results = await asyncio.gather(
        process_profile_res(user_id, user_memo_str, profile_config, config),
        process_event_res(user_id, user_memo_str, event_gists, profile_config, config),
        return_exceptions=True
    )

    if isinstance(processing_results[0], Exception):
        raise ExtractionError(f"Failed to process profile: {str(processing_results[0])}") from processing_results[0]
    if isinstance(processing_results[1], Exception):
        raise ExtractionError(f"Failed to process event: {str(processing_results[1])}") from processing_results[1]

    intermediate_profile, delta_profile_data = processing_results[0]
    event_data: EventProcessResult = processing_results[1]

    # Handle session events and user profiles (only skip if test_skip_persist is True)
    event_id = str(uuid.uuid4())
    persistence_results = await asyncio.gather(
        handle_session_event(
            user_id,
            event_id,
            user_memo_str,
            delta_profile_data,
            event_data.event_tags,
            config,
        ),
        handle_session_event_gists(
            user_id,
            event_id,
            event_data.event_gists_with_actions,
            config,
        ),
        handle_user_profile_db(user_id, intermediate_profile, config, project_id),
        return_exceptions=True
    )

    errors = []
    for idx, result in enumerate(persistence_results):
        operation_name = ["session_event", "event_gists", "user_profile"][idx]
        if isinstance(result, Exception):
            error_msg = f"{operation_name} failed: {str(result)}"
            TRACE_LOG.error(user_id, error_msg)
            errors.append(error_msg)

    if errors:
        raise ExtractionError(f"Persistence errors: {'; '.join(errors)}")

    return ChatModalResponse(
        event_id=event_id,
        add_profiles=[str(uuid.uuid4()) for _ in intermediate_profile["add"]],
        update_profiles=[str(up["profile_id"]) for up in intermediate_profile["update"]],
        delete_profiles=[str(pid) for pid in intermediate_profile["delete"]],
    )


async def process_profile_res(
        user_id: str,
        user_memo_str: str,
        project_profiles: ProfileConfig,
        config: Config,
) -> tuple[MergeAddResult, list[dict]]:
    extracted_data = await extract_topics(user_id, user_memo_str, project_profiles, config)

    # 2. Merge it to thw whole profile
    intermediate_profile = await merge_or_valid_new_profile(
        user_id=user_id,
        fact_contents=extracted_data["fact_contents"],
        fact_attributes=extracted_data["fact_attributes"],
        profiles=extracted_data["profiles"],
        profile_config=project_profiles,
        total_profiles=extracted_data["total_profiles"],
        config=config,
    )

    delta_profile_data = [
        p for p in (intermediate_profile["add"] + intermediate_profile["update_delta"])
    ]

    # 3. Check if we need to organize profiles
    await organize_profiles(
        user_id=user_id,
        profile_options=intermediate_profile,
        config=project_profiles,
        main_config=config
    )

    # 4. Re-summary profiles if any slot is too big
    await re_summary(
        user_id=user_id,
        add_profile=intermediate_profile["add"],
        update_profile=intermediate_profile["update"],
        config=config,
    )

    return (intermediate_profile, delta_profile_data)


# async def process_event_res(
#     usr_id: str,
#     memo_str: str,
#     profile_config: ProfileConfig,
#     config: Config,
# ) -> Promise[list | None]:
#     p = await tag_event(profile_config, memo_str, config)
#     if not p.ok():
#         return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to tag event: {p.msg()}")
#     event_tags = p.data()
#     return Promise.resolve(event_tags)


async def process_event_res(
        user_id: str,
        memo_str: str,
        event_gists: list[EventGist],
        profile_config: ProfileConfig,
        config: Config,
) -> EventProcessResult:
    # event index
    event_tags = await tag_event(profile_config, memo_str, config)
    if len(event_gists) == 0:
        return EventProcessResult(
            event_tags=event_tags,
            event_gists_with_actions=[]
        )

    returned_events_with_actions = await handle_merge_or_validate_new_event_gists(
        user_id, event_gists, profile_config, config
    )

    return EventProcessResult(
        event_tags=event_tags,
        event_gists_with_actions=returned_events_with_actions
    )
