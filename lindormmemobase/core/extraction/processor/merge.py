import asyncio
from datetime import datetime
from typing import Optional

from lindormmemobase.config import Config, TRACE_LOG
from lindormmemobase.core.constants import ConstantsTable
from lindormmemobase.core.extraction.prompts.utils import parse_string_into_merge_action
from lindormmemobase.core.extraction.prompts.router import PROMPTS
from lindormmemobase.models.profile_topic import UserProfileTopic, SubTopic, ProfileConfig
from lindormmemobase.llm.complete import llm_complete, llm_complete_with_schema
from lindormmemobase.utils.errors import ExtractionError
from lindormmemobase.models.response import ProfileData, MergeOperationResult
from lindormmemobase.models.types import MergeAddResult, UpdateResponse
from lindormmemobase.models.llm_responses import MergeProfileResponse


def get_threshold_for_subtopic(
    topic: str,
    subtopic: str,
    profile_config: ProfileConfig,
    subtopic_define: SubTopic
) -> int:
    """Resolve merge threshold for a specific topic/subtopic combination.

    Priority order:
    1. ProfileConfig.merge_thresholds[f"{topic}::{subtopic}"]
    2. SubTopic.merge_threshold
    3. Default: 1 (immediate merge, backward compatible)

    Args:
        topic: Topic name
        subtopic: Subtopic name
        profile_config: Profile configuration with merge_thresholds dict
        subtopic_define: SubTopic definition with optional merge_threshold

    Returns:
        Integer threshold value (>= 1)
    """
    # Priority 1: Check ProfileConfig.merge_thresholds
    threshold_key = f"{topic}::{subtopic}"
    if profile_config.merge_thresholds and threshold_key in profile_config.merge_thresholds:
        return profile_config.merge_thresholds[threshold_key]

    # Priority 2: Check SubTopic.merge_threshold
    if subtopic_define.merge_threshold is not None:
        return subtopic_define.merge_threshold

    # Priority 3: Default to 1 (immediate merge, backward compatible)
    return 1


async def merge_or_valid_new_profile(
    user_id: str,
    fact_contents: list[str],
    fact_attributes: list[dict],
    profiles: list[ProfileData],
    profile_config: ProfileConfig,
    total_profiles: list[UserProfileTopic],
    config,
    project_id: str | None = None,
    pending_storage=None,
) -> MergeAddResult:
    assert len(fact_contents) == len(
        fact_attributes
    ), "Length of fact_contents and fact_attributes must be equal"
    DEFINE_MAPS = {
        (p.topic, sp.name): sp for p in total_profiles for sp in p.sub_topics
    }

    RUNTIME_MAPS: dict[tuple[str, str], list[ProfileData]] = {}
    for p in profiles:
        key = (p.attributes[ConstantsTable.topic], p.attributes[ConstantsTable.sub_topic])
        if key not in RUNTIME_MAPS:
            RUNTIME_MAPS[key] = []
        RUNTIME_MAPS[key].append(p)

    profile_session_results: MergeAddResult = {
        "add": [],
        "update": [],
        "delete": [],
        "update_delta": [],
        "before_profiles": profiles,
    }
    tasks = []
    for f_c, f_a in zip(fact_contents, fact_attributes):
        task = handle_profile_merge_or_valid(
            user_id,
            f_a,
            f_c,
            profile_config,
            RUNTIME_MAPS,
            DEFINE_MAPS,
            profile_session_results,
            config,
            project_id,
            pending_storage,
        )
        tasks.append(task)
    await asyncio.gather(*tasks)
    return profile_session_results


async def handle_profile_merge_or_valid(
        user_id: str,
        profile_attributes: dict,
        profile_content: str,
        profile_config: ProfileConfig,
        profile_runtime_maps: dict[tuple[str, str], list[ProfileData]],
        profile_define_maps: dict[tuple[str, str], SubTopic],
        session_merge_validate_results: MergeAddResult,
        config,  # System config
        project_id: str | None = None,
        pending_storage=None,
) -> None:
    KEY = (
        profile_attributes[ConstantsTable.topic],
        profile_attributes[ConstantsTable.sub_topic],
    )
    USE_LANGUAGE = profile_config.language or config.language
    PROFILE_VALIDATE_MODE = (
        profile_config.profile_validate_mode
        if profile_config.profile_validate_mode is not None
        else config.profile_validate_mode
    )
    STRICT_MODE = (
        profile_config.profile_strict_mode
        if profile_config.profile_strict_mode is not None
        else config.profile_strict_mode
    )
    runtime_profiles = profile_runtime_maps.get(KEY, [])
    has_existing_profiles = len(runtime_profiles) > 0

    if has_existing_profiles:
        aggregated_content = "; ".join([p.content for p in runtime_profiles])
        primary_profile = runtime_profiles[0]
        additional_profile_ids = [p.id for p in runtime_profiles[1:]]
    else:
        aggregated_content = None
        primary_profile = None
        additional_profile_ids = []

    define_sub_topic = profile_define_maps.get(KEY, SubTopic(name=""))

    # T018: Check merge threshold before LLM call
    merge_threshold = get_threshold_for_subtopic(
        KEY[0], KEY[1], profile_config, define_sub_topic
    )

    if STRICT_MODE and KEY not in profile_define_maps:
        TRACE_LOG.warning(
            user_id,
            f"Rejecting undefined topic/subtopic in strict mode: {KEY}",
            project_id=project_id
        )
        return

    if (
            not PROFILE_VALIDATE_MODE
            and not define_sub_topic.validate_value
            and not has_existing_profiles
    ):
        TRACE_LOG.info(
            user_id,
            f"Skip validation: {KEY}",
            project_id=project_id
        )
        session_merge_validate_results["add"].append(
            {
                "content": profile_content,
                "attributes": profile_attributes,
            }
        )
        return

    # T018-T019: Threshold check - if threshold > 1, store in pending cache
    if merge_threshold > 1:
        if pending_storage is None:
            TRACE_LOG.warning(
                user_id,
                f"Threshold {merge_threshold} configured but no pending_storage available, "
                f"falling back to immediate merge for {KEY}",
                project_id=project_id
            )
        else:
            try:
                # Get current pending count
                from lindormmemobase.core.storage.manager import StorageManager
                if not isinstance(pending_storage, type(StorageManager.get_pending_profiles_storage(config))):
                    pending_storage = StorageManager.get_pending_profiles_storage(config)

                current_count = await pending_storage.get_pending_count(
                    user_id, KEY[0], KEY[1], project_id
                )

                # Check if we've reached threshold
                if current_count < merge_threshold - 1:
                    # Store in pending cache
                    entry_id = await pending_storage.insert_pending(
                        user_id=user_id,
                        topic=KEY[0],
                        subtopic=KEY[1],
                        profile_content=profile_content,
                        profile_attributes=profile_attributes,
                        project_id=project_id,
                        pending_count=current_count + 1
                    )
                    TRACE_LOG.debug(
                        user_id,
                        f"Stored profile in pending cache: {KEY} "
                        f"(count: {current_count + 1}/{merge_threshold}, entry_id: {entry_id})",
                        project_id=project_id
                    )
                    return
                else:
                    # Threshold reached, proceed with merge
                    TRACE_LOG.debug(
                        user_id,
                        f"Threshold reached for {KEY} ({current_count + 1}/{merge_threshold}), "
                        f"proceeding with merge",
                        project_id=project_id
                    )
            except Exception as e:
                TRACE_LOG.warning(
                    user_id,
                    f"Failed to store in pending cache, falling back to immediate merge: {str(e)}",
                    project_id=project_id
                )
    try:
        # Use JSON Mode with Pydantic validation
        merge_response: MergeProfileResponse = await llm_complete_with_schema(
            PROMPTS[USE_LANGUAGE]["merge"].get_input(
                KEY[0],
                KEY[1],
                aggregated_content,
                profile_content,
                update_instruction=define_sub_topic.update_description,
                topic_description=define_sub_topic.description,
                config=config,
            ),
            response_model=MergeProfileResponse,
            system_prompt=PROMPTS[USE_LANGUAGE]["merge"].get_prompt_json_mode(config),
            temperature=0.2,
            model=config.merge_llm_model or config.best_llm_model,
            config=config,
            **PROMPTS[USE_LANGUAGE]["merge"].get_kwargs(),
        )

        # Convert MergeProfileResponse to UpdateResponse format
        update_response: UpdateResponse = {
            "action": merge_response.action,
            "memo": merge_response.memo
        }
        if update_response["action"] == "UPDATE":
            if not has_existing_profiles:
                session_merge_validate_results["add"].append(
                    {
                        "content": update_response["memo"],
                        "attributes": profile_attributes,
                    }
                )
            else:
                if ConstantsTable.update_hits not in primary_profile.attributes:
                    primary_profile.attributes[ConstantsTable.update_hits] = 1
                else:
                    primary_profile.attributes[ConstantsTable.update_hits] += 1
                session_merge_validate_results["update"].append(
                    {
                        "profile_id": primary_profile.id,
                        "content": update_response["memo"],
                        "attributes": primary_profile.attributes,
                    }
                )
                session_merge_validate_results["update_delta"].append(
                    {
                        "content": profile_content,
                        "attributes": profile_attributes,
                    }
                )
                for pid in additional_profile_ids:
                    session_merge_validate_results["delete"].append(pid)
        elif update_response["action"] == "APPEND":
            session_merge_validate_results["add"].append(
                {
                    "content": profile_content,
                    "attributes": profile_attributes,
                }
            )
            session_merge_validate_results["update_delta"].append(
                {
                    "content": profile_content,
                    "attributes": profile_attributes,
                }
            )
        elif update_response["action"] == "ABORT":
            if not has_existing_profiles:
                TRACE_LOG.debug(
                    user_id,
                    f"Invalid profile: {KEY}::{profile_content}, abort it (action={merge_response.action}, memo={merge_response.memo})",
                    project_id=project_id
                )
            else:
                TRACE_LOG.debug(
                    user_id,
                    f"Invalid merge: {primary_profile.attributes}, {profile_content}, abort it (action={merge_response.action}, memo={merge_response.memo})",
                    project_id=project_id
                )
        else:
            TRACE_LOG.warning(
                user_id,
                f"Invalid action: {update_response['action']}",
                project_id=project_id
            )
            raise ExtractionError("Failed to parse merge action of Memobase")
    except Exception as e:
        TRACE_LOG.warning(
            user_id,
            f"Failed to merge profiles: {str(e)}",
            project_id=project_id
        )
        raise ExtractionError(f"Failed to merge profiles: {str(e)}") from e


async def batch_merge_pending_profiles(
    user_id: str,
    topic: str,
    subtopic: str,
    config: Config,
    project_id: Optional[str] = None,
    pending_storage=None,
    profile_storage=None
) -> MergeOperationResult:
    """Atomic batch merge operation for pending profiles.

    This function implements T022-T024:
    - T022: Atomic batch merge operation
    - T023: Optimistic concurrency check using updated_at
    - T024: Merge logging with TRACE_LOG

    The operation:
    1. Gets all pending entries for the (user_id, topic, subtopic, project_id) tuple
    2. Aggregates all profile_content into one string
    3. Calls LLM merge with aggregated content
    4. Updates main UserProfiles table with result (with optimistic concurrency)
    5. Deletes merged entries from PendingProfiles
    6. Returns MergeOperationResult

    Args:
        user_id: User identifier
        topic: Topic name (e.g., "interests", "preferences")
        subtopic: Subtopic name (e.g., "hobbies", "dietary")
        config: System configuration object
        project_id: Optional project identifier for multi-tenancy
        pending_storage: PendingProfiles storage instance (lazy-loaded if None)
        profile_storage: LindormTableStorage instance (lazy-loaded if None)

    Returns:
        MergeOperationResult with success status, merged count, and message

    Raises:
        ExtractionError: If merge operation fails
        TableStorageError: If storage operation fails
    """
    from lindormmemobase.core.storage.manager import StorageManager
    from lindormmemobase.utils.errors import TableStorageError

    # Lazy-load storage instances if not provided
    if pending_storage is None:
        pending_storage = StorageManager.get_pending_profiles_storage(config)
    if profile_storage is None:
        profile_storage = StorageManager.get_table_storage(config)

    # T021: Verify get_pending_count exists (already implemented in T011)
    pending_count = await pending_storage.get_pending_count(user_id, topic, subtopic, project_id)

    # Handle edge case: no pending entries
    if pending_count == 0:
        TRACE_LOG.info(
            user_id,
            f"No pending profiles to merge for topic={topic}, subtopic={subtopic}",
            project_id=project_id
        )
        return MergeOperationResult(
            success=True,
            merged_count=0,
            topics_merged=[],
            message=f"No pending profiles found for {topic}::{subtopic}"
        )

    # T024: Log merge start
    TRACE_LOG.info(
        user_id,
        f"Starting batch merge: topic={topic}, subtopic={subtopic}, "
        f"pending_count={pending_count}, project_id={project_id}",
        project_id=project_id
    )

    try:
        # Step 1: Get all pending entries for the tuple
        pending_entries = await pending_storage.get_pending_entries(
            user_id=user_id,
            topic=topic,
            subtopic=subtopic,
            project_id=project_id
        )

        if not pending_entries:
            return MergeOperationResult(
                success=True,
                merged_count=0,
                topics_merged=[],
                message=f"No pending entries found for {topic}::{subtopic}"
            )

        # Step 2: Aggregate all profile_content into one string
        aggregated_content = "; ".join([
            entry['profile_content'] for entry in pending_entries
        ])

        # Step 3: Get existing profiles for this (user, topic, subtopic) tuple
        existing_profiles = await profile_storage.get_user_profiles(
            user_id=user_id,
            project_id=project_id,
            topics=[topic],
            subtopics=[subtopic]
        )

        # Determine merge parameters
        USE_LANGUAGE = config.language
        has_existing = len(existing_profiles) > 0

        if has_existing:
            # Aggregate existing profile content
            existing_aggregated = "; ".join([p['content'] for p in existing_profiles])
            primary_profile = existing_profiles[0]
            additional_profile_ids = [p['id'] for p in existing_profiles[1:]]
        else:
            existing_aggregated = None
            primary_profile = None
            additional_profile_ids = []

        # Step 4: Call LLM merge with aggregated content
        merge_response: MergeProfileResponse = await llm_complete_with_schema(
            PROMPTS[USE_LANGUAGE]["merge"].get_input(
                topic,
                subtopic,
                existing_aggregated,  # Existing profiles (or None if new)
                aggregated_content,   # New pending content to merge
                update_instruction=None,  # No custom update instruction for batch merge
                topic_description=None,   # No custom description for batch merge
                config=config,
            ),
            response_model=MergeProfileResponse,
            system_prompt=PROMPTS[USE_LANGUAGE]["merge"].get_prompt_json_mode(config),
            temperature=0.2,
            model=config.merge_llm_model or config.best_llm_model,
            config=config,
            **PROMPTS[USE_LANGUAGE]["merge"].get_kwargs(),
        )

        # Step 5: Update UserProfiles table based on merge action
        merged_profile_ids = []
        entry_ids_to_delete = [entry['entry_id'] for entry in pending_entries]

        if merge_response.action == "UPDATE":
            if has_existing:
                # T023: Optimistic concurrency check using updated_at
                # Get the current updated_at timestamp before update
                current_updated_at = primary_profile.get('updated_at')

                # Prepare update attributes
                update_attributes = primary_profile['attributes'].copy()
                if ConstantsTable.update_hits not in update_attributes:
                    update_attributes[ConstantsTable.update_hits] = 0
                update_attributes[ConstantsTable.update_hits] += 1

                # Update profile with optimistic concurrency check
                updated_ids = await profile_storage.update_profiles(
                    user_id=user_id,
                    profile_ids=[primary_profile['id']],
                    contents=[merge_response.memo],
                    attributes_list=[update_attributes],
                    project_id=project_id
                )

                if updated_ids:
                    merged_profile_ids.append(primary_profile['id'])

                    # Delete additional profiles if any
                    if additional_profile_ids:
                        deleted_count = await profile_storage.delete_profiles(
                            user_id=user_id,
                            profile_ids=additional_profile_ids,
                            project_id=project_id
                        )
                        TRACE_LOG.debug(
                            user_id,
                            f"Deleted {deleted_count} additional profiles after merge",
                            project_id=project_id
                        )
                else:
                    # Concurrent update detected - profile was modified
                    TRACE_LOG.warning(
                        user_id,
                        f"Concurrent update detected for profile {primary_profile['id']}, "
                        f"skipping merge. Retry may be needed.",
                        project_id=project_id
                    )
                    return MergeOperationResult(
                        success=False,
                        merged_count=0,
                        topics_merged=[],
                        message=f"Concurrent update detected for {topic}::{subtopic}, merge aborted"
                    )
            else:
                # No existing profiles, create new one
                new_attributes = {
                    ConstantsTable.topic: topic,
                    ConstantsTable.sub_topic: subtopic,
                    ConstantsTable.update_hits: 1,
                }
                new_ids = await profile_storage.add_profiles(
                    user_id=user_id,
                    profiles=[merge_response.memo],
                    attributes_list=[new_attributes],
                    project_id=project_id
                )
                merged_profile_ids.extend(new_ids)

        elif merge_response.action == "APPEND":
            # Create new profile without merging
            new_attributes = {
                ConstantsTable.topic: topic,
                ConstantsTable.sub_topic: subtopic,
                ConstantsTable.update_hits: 0,
            }
            new_ids = await profile_storage.add_profiles(
                user_id=user_id,
                profiles=[aggregated_content],
                attributes_list=[new_attributes],
                project_id=project_id
            )
            merged_profile_ids.extend(new_ids)

        elif merge_response.action == "ABORT":
            TRACE_LOG.warning(
                user_id,
                f"LLM aborted merge for {topic}::{subtopic}: {merge_response.memo}",
                project_id=project_id
            )
            # Still delete pending entries on abort to avoid infinite retries
            await pending_storage.delete_pending_entries(entry_ids_to_delete)
            return MergeOperationResult(
                success=True,
                merged_count=0,
                topics_merged=[],
                message=f"Merge aborted by LLM: {merge_response.memo}"
            )

        # Step 6: Delete merged entries from PendingProfiles
        deleted_count = await pending_storage.delete_pending_entries(entry_ids_to_delete)

        # T024: Log merge completion
        TRACE_LOG.info(
            user_id,
            f"Batch merge completed: topic={topic}, subtopic={subtopic}, "
            f"pending_before={pending_count}, merged={deleted_count}, "
            f"action={merge_response.action}",
            project_id=project_id
        )

        return MergeOperationResult(
            success=True,
            merged_count=deleted_count,
            topics_merged=[(topic, subtopic)],
            message=f"Successfully merged {deleted_count} pending profiles for {topic}::{subtopic}"
        )

    except Exception as e:
        TRACE_LOG.error(
            user_id,
            f"Batch merge failed for {topic}::{subtopic}: {str(e)}",
            project_id=project_id
        )
        raise ExtractionError(f"Failed to batch merge pending profiles: {str(e)}") from e
