import asyncio
import uuid

from ....utils.tools import get_blob_str, get_encoded_tokens
from ....models.promise import Promise

from ....config import Config
from ....models.blob import Blob
from ....models.response import ChatModalResponse, CODE
from ....models.types import MergeAddResult
from ....models.profile_topic import ProfileConfig

from .extract import extract_topics
from .merge import merge_or_valid_new_memos
from .organize import organize_profiles
from .event_summary import tag_event
from .entry_summary import entry_chat_summary
from .summary import re_summary
from .profile_events import handle_session_event, handle_user_profile_db


def truncate_chat_blobs(
    blobs: list[Blob], max_token_size: int
) -> tuple[list[str], list[Blob]]:
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
    user_id: str, profile_config: ProfileConfig, blobs: list[Blob], config: Config
) -> Promise[ChatModalResponse]:
    # 1. Extract patch profiles
    blobs = truncate_chat_blobs(blobs, config.max_chat_blob_buffer_process_token_size)
    if len(blobs) == 0:
        return Promise.reject(
            CODE.SERVER_PARSE_ERROR, "No blobs to process after truncating"
        )

    p = await entry_chat_summary(blobs, profile_config, config)
    if not p.ok():
        return p
    user_memo_str = p.data()

    processing_results = await asyncio.gather(
        process_profile_res(user_id, user_memo_str, profile_config, config),
        process_event_res(user_id, user_memo_str, profile_config, config),
    )

    profile_results: Promise = processing_results[0]
    event_results: Promise = processing_results[1]

    if not profile_results.ok() or not event_results.ok():
        return Promise.reject(
            CODE.SERVER_PARSE_ERROR,
            f"Failed to process profile or event: {profile_results.msg()}, {event_results.msg()}",
        )

    intermediate_profile, delta_profile_data = profile_results.data()
    event_tags = event_results.data()

    # Handle session events and user profiles (only skip if test_skip_persist is True)
    if not config.test_skip_persist:  # Fixed: Changed to NOT config.test_skip_persist
        p = await handle_session_event(
            user_id,
            user_memo_str,
            delta_profile_data,
            event_tags,
            config,
        )
        if not p.ok():
            return p
        eid = p.data()

        p = await handle_user_profile_db(user_id, intermediate_profile, config)
        if not p.ok():
            return p
    else:
        # For testing: use mock event ID
        eid = str(uuid.uuid4())

    return Promise.resolve(
        ChatModalResponse(
            event_id=eid,
            add_profiles=[str(uuid.uuid4()) for _ in intermediate_profile["add"]],
            update_profiles=[up["profile_id"] for up in intermediate_profile["update"]],
            delete_profiles=intermediate_profile["delete"],
        )
    )


async def process_profile_res(
    user_id: str,
    user_memo_str: str,
    project_profiles: ProfileConfig,
    config: Config,
) -> Promise[tuple[MergeAddResult, list[dict]]]:

    p = await extract_topics(user_id, user_memo_str, project_profiles, config)
    if not p.ok():
        return p
    extracted_data = p.data()

    # 2. Merge it to thw whole profile
    p = await merge_or_valid_new_memos(
        user_id=user_id,
        fact_contents=extracted_data["fact_contents"],
        fact_attributes=extracted_data["fact_attributes"],
        profiles=extracted_data["profiles"],
        profile_config=project_profiles,
        total_profiles=extracted_data["total_profiles"],
        config=config,
    )
    if not p.ok():
        return p

    intermediate_profile = p.data()
    delta_profile_data = [
        p for p in (intermediate_profile["add"] + intermediate_profile["update_delta"])
    ]

    # 3. Check if we need to organize profiles
    p = await organize_profiles(
        user_id=user_id,
        profile_options=intermediate_profile,
        config=project_profiles,
        main_config=config
    )
    if not p.ok():
        return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to organize profiles: {p.msg()}")

    # 4. Re-summary profiles if any slot is too big
    p = await re_summary(
        user_id=user_id,
        add_profile=intermediate_profile["add"],
        update_profile=intermediate_profile["update"],
        config=config,
    )
    if not p.ok():
        return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to re-summary profiles: {p.msg()}")

    return Promise.resolve((intermediate_profile, delta_profile_data))


async def process_event_res(
    usr_id: str,
    memo_str: str,
    profile_config: ProfileConfig,
    config: Config,
) -> Promise[list | None]:
    p = await tag_event(profile_config, memo_str, config)
    if not p.ok():
        return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to tag event: {p.msg()}")
    event_tags = p.data()
    return Promise.resolve(event_tags)
