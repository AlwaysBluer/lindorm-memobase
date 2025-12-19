from httpx import AsyncClient
import httpx

_global_rerank_client = None
_global_rerank_config = None


def get_rerank_async_client_instance(config) -> AsyncClient:
    global _global_rerank_client, _global_rerank_config
    if _global_rerank_client is None or _global_rerank_config != config:
        _global_rerank_client = AsyncClient(
            base_url=config.rerank_base_url,
            headers={"Authorization": f"Bearer {config.rerank_api_key}"},
        )
        _global_rerank_config = config
    return _global_rerank_client


def get_lindormai_rerank_async_client_instance(config) -> AsyncClient:
    ak = config.lindorm_username
    sk = config.lindorm_password

    # Extract base URL without the full path
    # If rerank_base_url contains the full path, extract just the base
    base_url = config.rerank_base_url
    if "/dashscope/" in base_url:
        # Extract protocol + host + port
        parts = base_url.split("/dashscope/")
        base_url = parts[0]

    client = AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": "Bearer dummy",  # Required by DashScope API
            "x-ld-ak": ak,
            "x-ld-sk": sk,
        }
    )
    return client
