from .utils import exclude_special_kwargs, get_openai_async_client_instance
from ..config import LOG


async def openai_complete(
    model, prompt, system_prompt=None, history_messages=[], config=None, **kwargs
) -> str:
    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)

    openai_async_client = get_openai_async_client_instance(config)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    response = await openai_async_client.chat.completions.create(
        model=model, messages=messages, timeout=120, **kwargs
    )
    cached_tokens = getattr(response.usage.prompt_tokens_details, "cached_tokens", None)
    LOG.info(
        f"Cached {prompt_id} {model} {cached_tokens}/{response.usage.prompt_tokens}"
    )
    return response.choices[0].message.content


async def openai_stream_complete(
    model, prompt, system_prompt=None, history_messages=[], config=None, **kwargs
):
    """Stream completion from OpenAI API."""
    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)

    openai_async_client = get_openai_async_client_instance(config)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    # Enable streaming
    kwargs["stream"] = True

    try:
        response_stream = await openai_async_client.chat.completions.create(
            model=model, messages=messages, timeout=120, **kwargs
        )
        
        async for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        LOG.error(f"Error in streaming completion: {e}")
        raise
