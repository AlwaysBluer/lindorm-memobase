from openai import AsyncOpenAI

_global_openai_async_client = None
_global_config = None


def get_openai_async_client_instance(config) -> AsyncOpenAI:
    global _global_openai_async_client, _global_config
    if _global_openai_async_client is None or _global_config != config:
        _global_openai_async_client = AsyncOpenAI(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            default_query=config.llm_openai_default_query,
            default_headers=config.llm_openai_default_header,
        )
        _global_config = config
    return _global_openai_async_client


def exclude_special_kwargs(kwargs: dict):
    prompt_id = kwargs.pop("prompt_id", None)
    no_cache = kwargs.pop("no_cache", None)
    return {"prompt_id": prompt_id, "no_cache": no_cache}, kwargs
