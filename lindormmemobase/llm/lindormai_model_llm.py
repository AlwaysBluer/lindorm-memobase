from .utils import exclude_special_kwargs, get_lindormai_async_client_instance
from ..config import LOG


async def lindormai_complete(
        model, prompt, system_prompt=None, history_messages=[], config=None, **kwargs
) -> str:
    """Lindormai 完成请求（非流式）
    与 openai_complete 接口完全一致，只是使用不同的客户端
    """
    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)

    lindormai_async_client = get_lindormai_async_client_instance(config)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    try:
        response = await lindormai_async_client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=120,
            **kwargs
        )
        return response.choices[0].message.content

    except Exception as e:
        LOG.error(f"Error in Lindormai completion: {e}")
        raise
    finally:
        await lindormai_async_client.close()


async def lindormai_stream_complete(
        model, prompt, system_prompt=None, history_messages=[], config=None, **kwargs
):
    """Lindormai 流式完成请求

    与 openai_stream_complete 接口完全一致
    """
    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)

    lindormai_async_client = get_lindormai_async_client_instance(config)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    # 启用流式
    kwargs["stream"] = True

    try:
        response_stream = await lindormai_async_client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=120,
            **kwargs
        )

        async for chunk in response_stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        LOG.error(f"Error in Lindormai streaming completion: {e}")
        raise
    finally:
        await lindormai_async_client.close()
