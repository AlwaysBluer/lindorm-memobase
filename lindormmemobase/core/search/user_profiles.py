import json
import re
from typing import Optional, List
from lindormmemobase.config import Config, TRACE_LOG
from lindormmemobase.core.extraction.prompts import pick_related_profiles as pick_prompt
from lindormmemobase.llm.complete import llm_complete
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.models.response import UserProfilesData
from lindormmemobase.utils.tools import get_encoded_tokens, truncate_string, find_list_int_or_none
from lindormmemobase.utils.errors import SearchError

from lindormmemobase.core.storage.user_profiles import get_user_profiles

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
) -> UserProfilesData:
    if not len(profiles.profiles):
        return profiles
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
    return profiles


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
        project_id: Optional[str] = None,
) -> tuple[str, list]:
    """Retrieve and process user profiles."""
    total_profiles = await get_user_profiles(user_id, global_config, project_id=project_id)

    if max_profile_token_size > 0:
        if chats and (not full_profile_and_only_search_event):
            try:
                filter_result = await filter_profiles_with_chats(
                    user_id,
                    total_profiles,
                    chats,
                    global_config,
                    only_topics=only_topics,
                )
                total_profiles.profiles = filter_result["profiles"]
            except Exception as e:
                # If filtering fails, continue with all profiles
                TRACE_LOG.warning(user_id, f"Profile filtering failed: {str(e)}")

        user_profiles = total_profiles
        use_profiles = await truncate_profiles(
            user_profiles,
            prefer_topics=prefer_topics,
            only_topics=only_topics,
            max_token_size=max_profile_token_size,
            max_subtopic_size=max_subtopic_size,
            topic_limits=topic_limits,
        )
        use_profiles = use_profiles.profiles

        profile_section = "- " + "\n- ".join(
            [
                f"{p.attributes.get('topic')}::{p.attributes.get('sub_topic')}: {p.content}"
                for p in use_profiles
            ]
        )
    else:
        profile_section = ""
        use_profiles = []

    return (profile_section, use_profiles)


async def filter_profiles_with_chats(
        user_id: str,
        profiles: UserProfilesData,
        chats: list[OpenAICompatibleMessage],
        global_config: Config,
        only_topics: list[str] | None = None,
        max_value_token_size: int = 10,
        max_previous_chats: int = 4,
        max_filter_num: int = 10,
) -> dict:
    """Filter profiles with chats"""
    if not len(chats) or not len(profiles.profiles):
        raise SearchError("No chats or profiles to filter")
    chats = chats[-(max_previous_chats + 1):]
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
    try:
        r = await llm_complete(
            input_prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # precise
            model=global_config.summary_llm_model,
            config=global_config,
            **pick_prompt.get_kwargs(),
        )
        found_ids = find_list_int_or_none(r)
        reason = try_json_reason(r)
        if found_ids is None:
            TRACE_LOG.error(
                user_id,
                f"Failed to pick related profiles: {r}",
            )
            raise SearchError("Failed to pick related profiles")
        ids = [i for i in found_ids if i < len(topics_index)]
        profiles = [profiles.profiles[topics_index[i]["index"]] for i in ids]
        TRACE_LOG.info(
            user_id,
            f"Filter profiles with chats: {reason}, {found_ids}",
        )
        return {"reason": reason, "profiles": profiles}
    except Exception as e:
        TRACE_LOG.error(
            user_id,
            f"Failed to pick related profiles: {str(e)}",
        )
        raise SearchError(f"Failed to pick related profiles: {str(e)}") from e


async def search_profiles_by_embedding(
    user_id: str,
    query: str,
    global_config: Config,
    topk: int = 10,
    min_score: float = 0.5,
    project_id: Optional[str] = None,
    topics: Optional[list[str]] = None,
    subtopics: Optional[list[str]] = None
) -> UserProfilesData:
    """Search profiles using vector similarity.
    
    Args:
        user_id: User identifier
        query: Search query text
        global_config: Configuration object
        topk: Maximum number of results to return
        min_score: Minimum similarity score threshold
        project_id: Optional project filter
        topics: Optional topic filter (OR logic)
        subtopics: Optional subtopic filter (OR logic)
    
    Returns:
        UserProfilesData with matching profiles
    """
    from lindormmemobase.embedding import get_embedding
    from lindormmemobase.core.storage.user_profiles import get_lindorm_table_storage
    
    query_embeddings = await get_embedding([query], phase="query", config=global_config)
    query_vector = query_embeddings[0].tolist()
    
    storage = get_lindorm_table_storage(global_config)
    results = await storage.vector_search_profiles(
        user_id=user_id,
        query=query,
        query_vector=query_vector,
        size=topk,
        min_score=min_score,
        project_id=project_id,
        topics=topics,
        subtopics=subtopics
    )
    
    return UserProfilesData(profiles=results)


async def search_profiles_with_rerank(
    user_id: str,
    query: str,
    global_config: Config,
    topk: int = 10,
    project_id: Optional[str] = None,
    topics: Optional[list[str]] = None,
    combine_by_topic: bool = True
) -> UserProfilesData:
    """Search profiles using rerank model.
    
    Args:
        user_id: User identifier
        query: Search query text
        global_config: Configuration object
        topk: Maximum number of results to return
        project_id: Optional project filter
        topics: Optional topic filter
        combine_by_topic: If True, combine profiles by topic::subtopic before reranking
    
    Returns:
        UserProfilesData with reranked profiles
    """
    from lindormmemobase.rerank import get_rerank
    
    all_profiles = await get_user_profiles(user_id, global_config, project_id=project_id, topics=topics)
    
    if not all_profiles.profiles:
        return UserProfilesData(profiles=[])
    
    if combine_by_topic:
        grouped = {}
        for p in all_profiles.profiles:
            key = f"{p.attributes.get('topic', '')}::{p.attributes.get('sub_topic', '')}"
            if key not in grouped:
                grouped[key] = {
                    'profiles': [],
                    'contents': [],
                    'latest_updated': None
                }
            grouped[key]['profiles'].append(p)
            grouped[key]['contents'].append(p.content)
            updated = p.updated_at
            if grouped[key]['latest_updated'] is None or (updated and updated > grouped[key]['latest_updated']):
                grouped[key]['latest_updated'] = updated
        
        documents = []
        doc_keys = []
        for key, data in grouped.items():
            combined_content = "\n".join(data['contents'])
            documents.append(f"{key}: {combined_content}")
            doc_keys.append(key)
        
        rerank_results = await get_rerank(
            query=query,
            documents=documents,
            top_n=topk,
            config=global_config
        )
        
        result_profiles = []
        for r in rerank_results:
            key = doc_keys[r.index]
            result_profiles.extend(grouped[key]['profiles'])
        
        return UserProfilesData(profiles=result_profiles[:topk * 3])
    else:
        documents = [
            f"{p.attributes.get('topic', '')}::{p.attributes.get('sub_topic', '')}: {p.content}"
            for p in all_profiles.profiles
        ]
        
        rerank_results = await get_rerank(
            query=query,
            documents=documents,
            top_n=topk,
            config=global_config
        )
        
        result_profiles = [all_profiles.profiles[r.index] for r in rerank_results]
        return UserProfilesData(profiles=result_profiles)


async def hybrid_search_profiles(
    user_id: str,
    query: str,
    global_config: Config,
    embedding_topk: int = 30,
    final_topk: int = 10,
    min_score: float = 0.3,
    project_id: Optional[str] = None,
    topics: Optional[list[str]] = None
) -> UserProfilesData:
    """Search profiles using embedding + rerank hybrid approach.
    
    First retrieves candidates using vector search, then reranks them.
    
    Args:
        user_id: User identifier
        query: Search query text
        global_config: Configuration object
        embedding_topk: Number of candidates to retrieve from vector search
        final_topk: Final number of results after reranking
        min_score: Minimum similarity score for embedding search
        project_id: Optional project filter
        topics: Optional topic filter
    
    Returns:
        UserProfilesData with reranked profiles
    """
    from lindormmemobase.rerank import get_rerank
    
    embedding_results = await search_profiles_by_embedding(
        user_id=user_id,
        query=query,
        global_config=global_config,
        topk=embedding_topk,
        min_score=min_score,
        project_id=project_id,
        topics=topics
    )
    
    if not embedding_results.profiles:
        return UserProfilesData(profiles=[])
    
    documents = [
        f"{p.get('attributes', {}).get('topic', '')}::{p.get('attributes', {}).get('sub_topic', '')}: {p.get('content', '')}"
        if isinstance(p, dict) else
        f"{p.attributes.get('topic', '')}::{p.attributes.get('sub_topic', '')}: {p.content}"
        for p in embedding_results.profiles
    ]
    
    rerank_results = await get_rerank(
        query=query,
        documents=documents,
        top_n=final_topk,
        config=global_config
    )
    
    result_profiles = [embedding_results.profiles[r.index] for r in rerank_results]
    return UserProfilesData(profiles=result_profiles)
