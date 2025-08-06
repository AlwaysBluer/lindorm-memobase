from functools import partial

from ...config import Config, TRACE_LOG
from ...models.response import CODE
from ...models.blob import OpenAICompatibleMessage
from ...models.response import ContextData
from ...models.profile_topic import ProfileConfig
from ..extraction.prompts.chat_context_pack import CONTEXT_PROMPT_PACK

from ...models.promise import Promise
from ...utils.tools import get_encoded_tokens

from .events import get_user_event_gists_data, truncate_event_gists
from .user_profiles import get_user_profiles_data


def customize_context_prompt_func(
    context_prompt: str, profile_section: str, event_section: str
) -> str:
    return context_prompt.format(
        profile_section=profile_section, event_section=event_section
    )


async def get_user_context(
    user_id: str,
    profile_config: ProfileConfig,
    global_config: Config,
    max_token_size: int = 1000,
    prefer_topics: list[str] = None,
    only_topics: list[str] = None,
    max_subtopic_size: int = None,
    topic_limits: dict[str, int] = {},
    profile_event_ratio: float = 0.6,
    require_event_summary: bool = False,
    chats: list[OpenAICompatibleMessage] = [],
    event_similarity_threshold: float = 0.2,
    time_range_in_days: int = 180,
    customize_context_prompt: str = None,
    full_profile_and_only_search_event: bool = False,
    fill_window_with_events: bool = False,
) -> Promise[ContextData]:
    import asyncio

    assert 0 < profile_event_ratio <= 1, "profile_event_ratio must be between 0 and 1"
    max_profile_token_size = int(max_token_size * profile_event_ratio)

    use_language = profile_config.language or global_config.language
    context_prompt_func = CONTEXT_PROMPT_PACK[use_language]
    if customize_context_prompt is not None:
        context_prompt_func = partial(
            customize_context_prompt_func, customize_context_prompt
        )

    # Execute profile and event retrieval in parallel
    profile_result, event_gist_result = await asyncio.gather(
        get_user_profiles_data(
            user_id,
            max_profile_token_size,
            prefer_topics,
            only_topics,
            max_subtopic_size,
            topic_limits,
            chats,
            full_profile_and_only_search_event,
            global_config,
        ),
        get_user_event_gists_data(
            user_id,
            chats,
            require_event_summary,
            event_similarity_threshold,
            time_range_in_days,
            global_config,
        ),
        return_exceptions=True,
    )

    # Handle profile result
    if isinstance(profile_result, Exception):
        return Promise.reject(
            CODE.SERVER_PARSE_ERROR, f"Profile retrieval failed: {str(profile_result)}"
        )
    if not profile_result.ok():
        return profile_result
    profile_section, use_profiles = profile_result.data()

    # Handle event result
    if isinstance(event_gist_result, Exception):
        return Promise.reject(
            CODE.SERVER_PARSE_ERROR, f"Event retrieval failed: {str(event_gist_result)}"
        )
    if not event_gist_result.ok():
        return event_gist_result
    user_event_gists = event_gist_result.data()

    # Calculate token sizes and truncate events if needed
    profile_section_tokens = len(get_encoded_tokens(profile_section))
    if fill_window_with_events:
        max_event_token_size = max_token_size - profile_section_tokens
    else:
        max_event_token_size = min(
            max_token_size - profile_section_tokens,
            max_token_size - max_profile_token_size,
        )

    if max_event_token_size <= 0:
        return Promise.resolve(
            ContextData(context=context_prompt_func(profile_section, ""))
        )

    # Truncate events based on calculated token size
    p = await truncate_event_gists(user_event_gists, max_event_token_size)
    if not p.ok():
        return p
    user_event_gists = p.data()

    event_section = "\n".join([ed.gist_data.content for ed in user_event_gists.gists])
    event_section_tokens = len(get_encoded_tokens(event_section))

    TRACE_LOG.info(
        user_id,
        f"Retrieved {len(use_profiles)} profiles({profile_section_tokens} tokens), {len(user_event_gists.gists)} event gists({event_section_tokens} tokens)",
    )

    return Promise.resolve(
        ContextData(context=context_prompt_func(profile_section, event_section))
    )
