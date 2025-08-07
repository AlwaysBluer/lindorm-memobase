import asyncio
import time
from ..config import LOG
from ..utils.tools import Promise, CODE
from ..core.extraction.prompts.utils import convert_response_to_json
from . import FACTORIES


async def llm_complete(
    prompt,
    system_prompt=None,
    history_messages=[],
    json_mode=False,
    model=None,
    max_tokens=1024,
    config=None,
    **kwargs,
) -> Promise[str | dict]:
    if config is None:
        raise ValueError("config parameter is required")
    
    use_model = model or config.best_llm_model
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        start_time = time.time()
        results = await FACTORIES[config.llm_style](
            use_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            max_tokens=max_tokens,
            config=config,
            **kwargs,
        )
        latency = (time.time() - start_time) * 1000
    except Exception as e:
        LOG.error(f"Error in llm_complete: {e}")
        return Promise.reject(CODE.SERVICE_UNAVAILABLE, f"Error in llm_complete: {e}")

    if not json_mode:
        return Promise.resolve(results)
    parse_dict = convert_response_to_json(results)
    if parse_dict is not None:
        return Promise.resolve(parse_dict)
    else:
        return Promise.reject(
            CODE.UNPROCESSABLE_ENTITY, "Failed to parse JSON response"
        )


async def llm_stream_complete(
    prompt,
    system_prompt=None,
    history_messages=[],
    model=None,
    max_tokens=1024,
    config=None,
    **kwargs,
):
    """Stream completion from LLM."""
    if config is None:
        raise ValueError("config parameter is required")
    
    use_model = model or config.best_llm_model
    
    try:
        # Import the streaming function based on llm_style
        if config.llm_style == "openai":
            from .openai_model_llm import openai_stream_complete
            stream_func = openai_stream_complete
        else:
            raise ValueError(f"Streaming not supported for llm_style: {config.llm_style}")
        
        async for chunk in stream_func(
            use_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            max_tokens=max_tokens,
            config=config,
            **kwargs,
        ):
            yield chunk
            
    except Exception as e:
        LOG.error(f"Error in llm_stream_complete: {e}")
        raise