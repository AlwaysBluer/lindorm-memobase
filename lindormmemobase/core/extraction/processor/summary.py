import asyncio
from ....config import TRACE_LOG

from ....utils.tools import get_encoded_tokens, truncate_string
from ....utils.errors import ExtractionError

from ....models.types import AddProfile, UpdateProfile

from ....llm.complete import llm_complete
from ....core.extraction.prompts import summary_profile



async def re_summary(
    user_id: str,
    add_profile: list[AddProfile],
    update_profile: list[UpdateProfile],
    config,
) -> None:
    add_tasks = [summary_memo(user_id, ap, config) for ap in add_profile]
    await asyncio.gather(*add_tasks, return_exceptions=True)
    update_tasks = [summary_memo(user_id, up, config) for up in update_profile]
    results = await asyncio.gather(*update_tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        raise ExtractionError(f"Failed to re-summary profiles: {errors[0]}") from errors[0]


async def summary_memo(
    user_id: str, content_pack: dict, config
) -> None:
    content = content_pack["content"]
    if len(get_encoded_tokens(content)) <= config.max_pre_profile_token_size:
        return
    
    target_tokens = config.max_pre_profile_token_size
    
    try:
        r = await llm_complete(
            content_pack["content"],
            system_prompt=summary_profile.get_prompt(max_tokens=target_tokens),
            temperature=0.1, 
            model=config.summary_llm_model,
            config=config,
            **summary_profile.get_kwargs(),
        )
        
        # Verify the LLM output length
        result_tokens = len(get_encoded_tokens(r))
        
        if result_tokens <= target_tokens:
            # LLM successfully controlled the length
            content_pack["content"] = r
        else:
            # Fallback: LLM exceeded limit, apply soft truncation
            TRACE_LOG.warning(
                user_id,
                f"LLM summary exceeded target ({result_tokens} > {target_tokens}), applying truncation"
            )
            content_pack["content"] = truncate_string(r, target_tokens)
            
    except Exception as e:
        TRACE_LOG.error(
            user_id, 
            f"Failed to summary memo: {str(e)}",
        )
        raise ExtractionError(f"Failed to summary memo: {str(e)}") from e
