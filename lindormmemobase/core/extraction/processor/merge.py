import asyncio
import json

import numpy

from ...search.events import search_user_event_gists, search_user_event
from ...storage.events import search_user_event_gists_with_embedding
from ....config import TRACE_LOG
from ....core.constants import ConstantsTable
from ....core.extraction.prompts.utils import parse_string_into_merge_action
from ....core.extraction.prompts.router import PROMPTS, UpdateResponse
from ....embedding import get_embedding
from ....models.profile_topic import UserProfileTopic, SubTopic, ProfileConfig
from ....llm.complete import llm_complete
from ....utils.errors import ExtractionError
from ....models.response import ProfileData, UserEventGistsData, EventGist, EventGistWithAction
from ....models.types import MergeAddResult
from ....utils.text_utils import remove_code_blocks


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
    runtime_profile = profile_runtime_maps.get(KEY, None)
    define_sub_topic = profile_define_maps.get(KEY, SubTopic(name=""))

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
            ),
            system_prompt=PROMPTS[USE_LANGUAGE]["merge"].get_prompt(),
            temperature=0.2,
            config=config,
            **PROMPTS[USE_LANGUAGE]["merge"].get_kwargs(),
        )
        # print(KEY, profile_content)
        # print(r)
        update_response: UpdateResponse | None = parse_string_into_merge_action(r)
        if update_response is None:
            TRACE_LOG.warning(
                user_id,
                f"Failed to parse merge action: {r}",
            )
            raise ExtractionError("Failed to parse merge action of Memobase")
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
                        "content": f"{runtime_profile.content};; {profile_content}",
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
                TRACE_LOG.info(
                    user_id,
                    f"Invalid profile: {KEY}::{profile_content}, abort it\n<raw_response>\n{r}\n</raw_response>",
                )
            else:
                TRACE_LOG.info(
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


async def handle_merge_or_validate_new_event_gists(
        user_id: str,
        event_gists: list[EventGist],
        profile_config: ProfileConfig,
        config,
) -> list:
    """
    对单个query，由LLM进行判断增加，删除，改造，并返回处理结果
    """
    if len(event_gists) == 0:
        return []

    USE_LANGUAGE = profile_config.language or config.language

    tasks = [
        process_single_event_gist(user_id, eg, USE_LANGUAGE, config)
        for eg in event_gists
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            TRACE_LOG.error(
                user_id,
                f"Failed to process event gist {idx}: {str(result)}"
            )
            # 添加 ABORT 作为降级处理
            all_results.append(EventGistWithAction(
                text=event_gists[idx].text,
                embedding=event_gists[idx].embedding,
                action="ABORT",
            ))
        elif isinstance(result, list):
            all_results.extend(result)
        else:
            TRACE_LOG.warning(user_id, f"Unexpected result type: {type(result)}")

    return all_results


async def process_single_event_gist(
    user_id: str,
    eg: EventGist,
    language: str,
    config,
) -> list[EventGistWithAction]:
    """
        处理单个 event gist
    """
    # 1. 检查 embedding
    if eg.embedding is None:
        return [EventGistWithAction(
            text=eg.text,
            embedding=None,
            action="ABORT",
        )]

    # 2. 搜索相似的已有事件
    try:
        r = await search_user_event_gists_with_embedding(
            user_id=user_id,
            query=eg.text,
            query_vector=eg.embedding.tolist(),
            config=config,
            topk=5,
            similarity_threshold=0.6,
            time_range_in_days=100
        )
        existing_events = r
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to search event gists: {str(e)}")
        return [EventGistWithAction(
            text=eg.text,
            embedding=eg.embedding,
            action="ABORT",
        )]

    if not existing_events:
        return [EventGistWithAction(
            text=eg.text,
            embedding=eg.embedding,
            action="ADD",
            event_gist_id=None,
            similarity=None,
        )]

    # 4. 准备 LLM 输入
    retrieved_old_events = [
        {"id": e["id"], "text": e["gist_data"]}
        for e in existing_events
    ]

    temp_uuid_mapping = {}
    for idx, item in enumerate(retrieved_old_events):
        temp_uuid_mapping[str(idx)] = item["id"]
        retrieved_old_events[idx]["id"] = str(idx)

    # 5. 调用 LLM
    try:
        r = await llm_complete(
            PROMPTS[language]["merge_events"].get_input(
                eg.text,
                retrieved_old_events
            ),
            system_prompt=PROMPTS[language]["merge_events"].get_prompt(),
            temperature=0.2,
            config=config,
            **PROMPTS[language]["merge_events"].get_kwargs(),
        )
    except Exception as e:
        TRACE_LOG.error(user_id, f"Failed to complete merge events: {str(e)}")
        return [EventGistWithAction(
            text=eg.text,
            embedding=eg.embedding,
            action="ABORT",
        )]

    # 6. 解析 LLM 响应
    response = remove_code_blocks(r)
    if not response or not response.strip():
        TRACE_LOG.warning(user_id, f"Empty LLM response for event: {eg.text[:50]}...")
        return [EventGistWithAction(
            text=eg.text,
            embedding=eg.embedding,
            action="ABORT",
        )]

    try:
        new_events_with_actions = json.loads(response)
    except json.JSONDecodeError as e:
        TRACE_LOG.error(user_id, f"Failed to parse LLM response: {e}")
        return [EventGistWithAction(
            text=eg.text,
            embedding=eg.embedding,
            action="ABORT",
        )]

    # 7. 处理 LLM 返回的 actions
    results = []
    try:
        for resp in new_events_with_actions.get("memory", []):
            action_result = parse_llm_action(
                resp, eg, temp_uuid_mapping, user_id
            )
            if action_result:
                results.append(action_result)
    except Exception as e:
        TRACE_LOG.error(user_id, f"Error processing LLM response: {e}")

    return results if results else [EventGistWithAction(
        text=eg.text,
        embedding=eg.embedding,
        action="ABORT",
    )]


def parse_llm_action(
        resp: dict,
        eg: EventGist,
        temp_uuid_mapping: dict,
        user_id: str,
) -> EventGistWithAction | None:
    """
    解析单个 LLM action
    """
    try:
        action_text = resp.get("text")
        if not action_text:
            TRACE_LOG.info(user_id, "Skipping memory entry because of empty `text` field.")
            return None

        action_type = resp.get("action")

        if action_type == "ADD":
            return EventGistWithAction(
                text=action_text,
                embedding=eg.embedding,
                action="ADD",
                event_gist_id=None,
                similarity=None,
            )

        elif action_type == "UPDATE":
            temp_id = resp.get("id")
            real_event_id = temp_uuid_mapping.get(temp_id)
            if not real_event_id:
                TRACE_LOG.error(user_id, f"Invalid temp_id for UPDATE: {temp_id}")
                return None

            return EventGistWithAction(
                text=action_text,
                embedding=eg.embedding,
                action="UPDATE",
                event_gist_id=real_event_id,
                similarity=None,
            )

        elif action_type == "DELETE":
            temp_id = resp.get("id")
            real_event_id = temp_uuid_mapping.get(temp_id)
            if not real_event_id:
                TRACE_LOG.error(user_id, f"Invalid temp_id for DELETE: {temp_id}")
                return None

            return EventGistWithAction(
                text=action_text,
                embedding=None,
                action="DELETE",
                event_gist_id=real_event_id,
                similarity=None,
            )

        elif action_type == "ABORT":
            TRACE_LOG.info(user_id, f"LLM decided to abort event: {action_text[:50]}...")
            return EventGistWithAction(
                text=action_text,
                embedding=eg.embedding,
                action="ABORT",
                event_gist_id=None,
                similarity=None,
            )

        else:
            TRACE_LOG.warning(user_id, f"Invalid action type: {action_type}")
            return None

    except Exception as e:
        TRACE_LOG.error(user_id, f"Error parsing action: {resp}, Error: {e}")
        return None





