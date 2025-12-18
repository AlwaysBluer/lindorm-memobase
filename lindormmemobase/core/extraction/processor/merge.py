import asyncio

from lindormmemobase.config import TRACE_LOG
from lindormmemobase.core.constants import ConstantsTable
from lindormmemobase.core.extraction.prompts.utils import parse_string_into_merge_action
from lindormmemobase.core.extraction.prompts.router import PROMPTS
from lindormmemobase.models.profile_topic import UserProfileTopic, SubTopic, ProfileConfig
from lindormmemobase.llm.complete import llm_complete
from lindormmemobase.utils.errors import ExtractionError
from lindormmemobase.models.response import ProfileData
from lindormmemobase.models.types import MergeAddResult, UpdateResponse


async def merge_or_valid_new_profile(
        user_id: str,
        fact_contents: list[str],
        fact_attributes: list[dict],
        profiles: list[ProfileData],
        profile_config: ProfileConfig,
        total_profiles: list[UserProfileTopic],
        config,
) -> MergeAddResult:
    assert len(fact_contents) == len(
        fact_attributes
    ), "Length of fact_contents and fact_attributes must be equal"
    DEFINE_MAPS = {
        (p.topic, sp.name): sp for p in total_profiles for sp in p.sub_topics
    }

    RUNTIME_MAPS = {
        (p.attributes[ConstantsTable.topic], p.attributes[ConstantsTable.sub_topic]): p
        for p in profiles
    }

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
        )
        tasks.append(task)
    await asyncio.gather(*tasks)
    return profile_session_results


async def handle_profile_merge_or_valid(
        user_id: str,
        profile_attributes: dict,
        profile_content: str,
        profile_config: ProfileConfig,
        profile_runtime_maps: dict[tuple[str, str], ProfileData],
        profile_define_maps: dict[tuple[str, str], SubTopic],
        session_merge_validate_results: MergeAddResult,
        config,  # System config
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
    runtime_profile = profile_runtime_maps.get(KEY, None)
    define_sub_topic = profile_define_maps.get(KEY, SubTopic(name=""))
    
    # In strict mode, reject profiles with undefined topic/subtopic combinations
    if STRICT_MODE and KEY not in profile_define_maps:
        TRACE_LOG.warning(
            user_id,
            f"Rejecting undefined topic/subtopic in strict mode: {KEY}"
        )
        return

    if (
            not PROFILE_VALIDATE_MODE
            and not define_sub_topic.validate_value
            and runtime_profile is None
    ):
        TRACE_LOG.info(
            user_id,
            f"Skip validation: {KEY}",
        )
        session_merge_validate_results["add"].append(
            {
                "content": profile_content,
                "attributes": profile_attributes,
            }
        )
        return
    try:
        r = await llm_complete(
            PROMPTS[USE_LANGUAGE]["merge"].get_input(
                KEY[0],
                KEY[1],
                runtime_profile.content if runtime_profile else None,
                profile_content,
                update_instruction=define_sub_topic.update_description,  # maybe none
                topic_description=define_sub_topic.description,  # maybe none
                config=config,
            ),
            system_prompt=PROMPTS[USE_LANGUAGE]["merge"].get_prompt(config),
            temperature=0.2,
            model=config.merge_llm_model or config.best_llm_model,
            config=config,
            **PROMPTS[USE_LANGUAGE]["merge"].get_kwargs(),
        )
        # print(KEY, profile_content)
        # print(r)
        update_response: UpdateResponse = parse_string_into_merge_action(r)
        # parse_string_into_merge_action now always returns a dict (never None)
        # If parsing fails, it returns {"action": "ABORT", "memo": "ABORT"} with a warning log
        if update_response["action"] == "UPDATE":
            if runtime_profile is None:
                session_merge_validate_results["add"].append(
                    {
                        "content": update_response["memo"],
                        "attributes": profile_attributes,
                    }
                )
            else:
                if ConstantsTable.update_hits not in runtime_profile.attributes:
                    runtime_profile.attributes[ConstantsTable.update_hits] = 1
                else:
                    runtime_profile.attributes[ConstantsTable.update_hits] += 1
                session_merge_validate_results["update"].append(
                    {
                        "profile_id": runtime_profile.id,
                        "content": update_response["memo"],
                        "attributes": runtime_profile.attributes,
                    }
                )
                session_merge_validate_results["update_delta"].append(
                    {
                        "content": profile_content,
                        "attributes": profile_attributes,
                    }
                )
        elif update_response["action"] == "APPEND":
            if runtime_profile is None:
                session_merge_validate_results["add"].append(
                    {
                        "content": profile_content,
                        "attributes": profile_attributes,
                    }
                )
            else:
                if ConstantsTable.update_hits not in runtime_profile.attributes:
                    runtime_profile.attributes[ConstantsTable.update_hits] = 1
                else:
                    runtime_profile.attributes[ConstantsTable.update_hits] += 1
                # Use ;; separator to mark for later splitting
                session_merge_validate_results["update"].append(
                    {
                        "profile_id": runtime_profile.id,
                        "content": f"{runtime_profile.content};{profile_content}",
                        "attributes": runtime_profile.attributes,
                    }
                )
                session_merge_validate_results["update_delta"].append(
                    {
                        "content": profile_content,
                        "attributes": profile_attributes,
                    }
                )
        elif update_response["action"] == "ABORT":
            if runtime_profile is None:
                TRACE_LOG.debug(
                    user_id,
                    f"Invalid profile: {KEY}::{profile_content}, abort it\n<raw_response>\n{r}\n</raw_response>",
                )
            else:
                TRACE_LOG.debug(
                    user_id,
                    f"Invalid merge: {runtime_profile.attributes}, {profile_content}, abort it\n<raw_response>\n{r}\n</raw_response>",
                )
                # session_merge_validate_results["delete"].append(runtime_profile.id)
        else:
            TRACE_LOG.warning(
                user_id,
                f"Invalid action: {update_response['action']}",
            )
            raise ExtractionError("Failed to parse merge action of Memobase")
    except Exception as e:
        TRACE_LOG.warning(
            user_id,
            f"Failed to merge profiles: {str(e)}",
        )
        raise ExtractionError(f"Failed to merge profiles: {str(e)}") from e