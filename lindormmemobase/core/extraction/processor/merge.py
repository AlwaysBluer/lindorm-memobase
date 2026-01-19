import asyncio

from lindormmemobase.config import TRACE_LOG
from lindormmemobase.core.constants import ConstantsTable
from lindormmemobase.core.extraction.prompts.utils import parse_string_into_merge_action
from lindormmemobase.core.extraction.prompts.router import PROMPTS
from lindormmemobase.models.profile_topic import UserProfileTopic, SubTopic, ProfileConfig
from lindormmemobase.llm.complete import llm_complete, llm_complete_with_schema
from lindormmemobase.utils.errors import ExtractionError
from lindormmemobase.models.response import ProfileData
from lindormmemobase.models.types import MergeAddResult, UpdateResponse
from lindormmemobase.models.llm_responses import MergeProfileResponse


async def merge_or_valid_new_profile(
        user_id: str,
        fact_contents: list[str],
        fact_attributes: list[dict],
        profiles: list[ProfileData],
        profile_config: ProfileConfig,
        total_profiles: list[UserProfileTopic],
        config,
        project_id: str | None = None,
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