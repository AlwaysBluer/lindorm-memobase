from openai import AsyncOpenAI
import httpx

_global_openai_async_client = None
_global_config = None
_global_lindormai_async_client = None
_global_lindormai_config = None


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


def get_lindormai_async_client_instance(config=None):
    """Get or create global Lindormai async client instance.

    Lindormai uses OpenAI-compatible API with custom auth headers.
    Uses singleton pattern for connection reuse.
    """
    global _global_lindormai_async_client, _global_lindormai_config

    if _global_lindormai_async_client is None or _global_lindormai_config != config:
        base_url = config.llm_base_url
        ak = config.lindorm_username
        sk = config.lindorm_password

        # Configure explicit timeout to avoid gzip decode errors
        timeout = httpx.Timeout(120.0, connect=60.0)

        # Create custom httpx client with auth headers and timeout
        http_client = httpx.AsyncClient(
            headers={
                "x-ld-ak": ak,
                "x-ld-sk": sk,
            },
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

        # Use OpenAI SDK with custom base_url and http_client
        _global_lindormai_async_client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy",  # Lindormai does not use api_key, but SDK requires it
            http_client=http_client
        )
        _global_lindormai_config = config

    return _global_lindormai_async_client

def exclude_special_kwargs(kwargs: dict):
    prompt_id = kwargs.pop("prompt_id", None)
    no_cache = kwargs.pop("no_cache", None)
    return {"prompt_id": prompt_id, "no_cache": no_cache}, kwargs
