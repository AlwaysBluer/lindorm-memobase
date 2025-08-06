import json
import re
from ...config import Config, TRACE_LOG
from ..extraction.prompts import pick_related_profiles as pick_prompt
from ...llm.complete import llm_complete
from ...models.blob import OpenAICompatibleMessage
from ...models.response import UserProfilesData, CODE
from ...utils.promise import Promise
from ...utils.tools import get_encoded_tokens, truncate_string, find_list_int_or_none

from ..storage.user_profiles import get_user_profiles


JSON_BODY_REGEX = re.compile(r"({[\s\S]*})")

def try_json_reason(content: str) -> str | None:
    try:
        return json.loads(JSON_BODY_REGEX.search(content).group(1))["reason"]
    except Exception:
        return None


async def truncate_profiles(
    profiles: UserProfilesData,
    prefer_topics: list[str] = None,
    topk: int = None,
    max_token_size: int = None,
    only_topics: list[str] = None,
    max_subtopic_size: int = None,
    topic_limits: dict[str, int] = None,
) -> Promise[UserProfilesData]:
    if not len(profiles.profiles):
        return Promise.resolve(profiles)
    profiles.profiles.sort(key=lambda p: p.updated_at, reverse=True)
    if prefer_topics:
        prefer_topics = [t.strip() for t in prefer_topics]
        priority_weights = {t: i for i, t in enumerate(prefer_topics)}
        priority_profiles = []
        non_priority_profiles = []
        for p in profiles.profiles:
            if p.attributes.get("topic") in priority_weights:
                priority_profiles.append(p)
            else:
                non_priority_profiles.append(p)
        priority_profiles.sort(
            key=lambda p: priority_weights[p.attributes.get("topic")]
        )
        profiles.profiles = priority_profiles + non_priority_profiles
    if only_topics:
        only_topics = [t.strip() for t in only_topics]
        s_only_topics = set(only_topics)
        profiles.profiles = [
            p
            for p in profiles.profiles
            if p.attributes.get("topic").strip() in s_only_topics
        ]
    if max_subtopic_size or topic_limits:
        use_topic_limits = topic_limits or {}
        max_subtopic_size = max_subtopic_size or -1
        _count_subtopics = {}
        filtered_profiles = []
        for p in profiles.profiles:
            name_key = p.attributes.get("topic")
            this_topic_limit = use_topic_limits.get(name_key, max_subtopic_size)
            if name_key not in _count_subtopics:
                _count_subtopics[name_key] = 0
            _count_subtopics[name_key] += 1
            if this_topic_limit >= 0 and _count_subtopics[name_key] > this_topic_limit:
                continue
            filtered_profiles.append(p)
        profiles.profiles = filtered_profiles

    if topk:
        profiles.profiles = profiles.profiles[:topk]
    if max_token_size:
        current_length = 0
        use_index = 0
        for max_i, p in enumerate(profiles.profiles):
            single_p = f"{p.attributes.get('topic')}::{p.attributes.get('sub_topic')}: {p.content}"
            current_length += len(get_encoded_tokens(single_p))
            if current_length > max_token_size:
                break
            use_index = max_i
        profiles.profiles = profiles.profiles[: use_index + 1]
    return Promise.resolve(profiles)


async def get_user_profiles_data(
    user_id: str,
    max_profile_token_size: int,
    prefer_topics: list[str],
    only_topics: list[str],
    max_subtopic_size: int,
    topic_limits: dict[str, int],
    chats: list[OpenAICompatibleMessage],
    full_profile_and_only_search_event: bool,
    global_config: Config,
) -> Promise[tuple[str, list]]:
    """Retrieve and process user profiles."""
    p = await get_user_profiles(user_id, global_config)
    if not p.ok():
        return p
    total_profiles = p.data()

    if max_profile_token_size > 0:
        if chats and (not full_profile_and_only_search_event):
            p = await filter_profiles_with_chats(
                user_id,
                total_profiles,
                chats,
                global_config,
                only_topics=only_topics,
            )
            if p.ok():
                total_profiles.profiles = p.data()["profiles"]

        user_profiles = total_profiles
        use_profiles = await truncate_profiles(
            user_profiles,
            prefer_topics=prefer_topics,
            only_topics=only_topics,
            max_token_size=max_profile_token_size,
            max_subtopic_size=max_subtopic_size,
            topic_limits=topic_limits,
        )
        if not use_profiles.ok():
            return use_profiles
        use_profiles = use_profiles.data().profiles

        profile_section = "- " + "\n- ".join(
            [
                f"{p.attributes.get('topic')}::{p.attributes.get('sub_topic')}: {p.content}"
                for p in use_profiles
            ]
        )
    else:
        profile_section = ""
        use_profiles = []

    return Promise.resolve((profile_section, use_profiles))


async def filter_profiles_with_chats(
    user_id: str,
    profiles: UserProfilesData,
    chats: list[OpenAICompatibleMessage],
    global_config: Config,
    only_topics: list[str] | None = None,
    max_value_token_size: int = 10,
    max_previous_chats: int = 4,
    max_filter_num: int = 10,
) -> Promise[dict]:
    """Filter profiles with chats"""
    if not len(chats) or not len(profiles.profiles):
        return Promise.reject(CODE.BAD_REQUEST, "No chats or profiles to filter")
    chats = chats[-(max_previous_chats + 1) :]
    if only_topics:
        only_topics = [t.strip() for t in only_topics]
        only_topics = set(only_topics)

    topics_index = [
        {
            "index": i,
            "topic": p.attributes["topic"],
            "sub_topic": p.attributes["sub_topic"],
            "content": truncate_string(p.content, max_value_token_size),
        }
        for i, p in enumerate(profiles.profiles)
        if only_topics is None or p.attributes["topic"].strip() in only_topics
    ]

    topics_index = sorted(topics_index, key=lambda x: (x["topic"], x["sub_topic"]))
    system_prompt = pick_prompt.get_prompt(max_num=max_filter_num)
    input_prompt = pick_prompt.get_input(chats, topics_index)
    r = await llm_complete(
        input_prompt,
        system_prompt=system_prompt,
        temperature=0.2,  # precise
        model=global_config.summary_llm_model,
        config=global_config,
        **pick_prompt.get_kwargs(),
    )
    if not r.ok():
        TRACE_LOG.error(
            user_id,
            f"Failed to pick related profiles: {r.msg()}",
        )
        return r
    found_ids = find_list_int_or_none(r.data())
    reason = try_json_reason(r.data())
    if found_ids is None:
        TRACE_LOG.error(
            user_id,
            f"Failed to pick related profiles: {r.data()}",
        )
        return Promise.reject(
            CODE.INTERNAL_SERVER_ERROR, "Failed to pick related profiles"
        )
    ids = [i for i in found_ids if i < len(topics_index)]
    profiles = [profiles.profiles[topics_index[i]["index"]] for i in ids]
    TRACE_LOG.info(
        user_id,
        f"Filter profiles with chats: {reason}, {found_ids}",
    )
    return Promise.resolve({"reason": reason, "profiles": profiles})