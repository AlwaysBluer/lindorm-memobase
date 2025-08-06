import asyncio
from ....config import TRACE_LOG

from ....models.promise import Promise
from ....utils.tools import get_encoded_tokens, truncate_string

from ....models.types import AddProfile, UpdateProfile

from ....llm.complete import llm_complete
from ....core.extraction.prompts import summary_profile



async def re_summary(
    user_id: str,
    add_profile: list[AddProfile],
    update_profile: list[UpdateProfile],
    config,
) -> Promise[None]:
    add_tasks = [summary_memo(user_id, ap, config) for ap in add_profile]
    await asyncio.gather(*add_tasks)
    update_tasks = [summary_memo(user_id, up, config) for up in update_profile]
    ps = await asyncio.gather(*update_tasks)
    if not all([p.ok() for p in ps]):
        return Promise.reject("Failed to re-summary profiles")
    return Promise.resolve(None)


async def summary_memo(
    user_id: str, content_pack: dict, config
) -> Promise[None]:
    content = content_pack["content"]
    if len(get_encoded_tokens(content)) <= config.max_pre_profile_token_size:
        return Promise.resolve(None)
    r = await llm_complete(
        content_pack["content"],
        system_prompt=summary_profile.get_prompt(),
        temperature=0.2, 
        model=config.summary_llm_model,
        config=config,
        **summary_profile.get_kwargs(),
    )
    if not r.ok():
        TRACE_LOG.error(
            user_id, 
            f"Failed to summary memo: {r.msg()}",
        )
        return r
    content_pack["content"] = truncate_string(
        r.data(), config.max_pre_profile_token_size // 2
    )
    return Promise.resolve(None)
