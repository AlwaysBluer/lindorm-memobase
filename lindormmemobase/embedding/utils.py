from openai import AsyncOpenAI
from httpx import AsyncClient
import httpx

_global_openai_async_client = None
_global_jina_async_client = None
_global_config = None


def get_openai_async_client_instance(config) -> AsyncOpenAI:
    global _global_openai_async_client, _global_config
    if _global_openai_async_client is None or _global_config != config:
        _global_openai_async_client = AsyncOpenAI(
            base_url=config.embedding_base_url,
            api_key=config.embedding_api_key,
        )
        _global_config = config
    return _global_openai_async_client


def get_jina_async_client_instance(config) -> AsyncClient:
    global _global_jina_async_client, _global_config
    if _global_jina_async_client is None or _global_config != config:
        _global_jina_async_client = AsyncClient(
            base_url=config.embedding_base_url,
            headers={"Authorization": f"Bearer {config.embedding_api_key}"},
        )
        _global_config = config
    return _global_jina_async_client

def get_lindormai_async_client_instance(config=None):
    """创建 Lindormai 异步客户端实例

    Lindormai 使用 OpenAI 兼容的 API，但使用自定义的鉴权头
    """
    base_url = config.embedding_base_url
    ak = config.lindorm_username
    sk = config.lindorm_password

    # 创建自定义 httpx 客户端，添加鉴权头
    http_client = httpx.AsyncClient(
        headers={
            "x-ld-ak": ak,
            "x-ld-sk": sk,
        }
    )

    # 使用 OpenAI SDK，但使用自定义的 base_url 和 http_client
    client = AsyncOpenAI(
        base_url=base_url,
        api_key="dummy",  # Lindormai 不使用 api_key，但 SDK 要求必须提供
        http_client=http_client
    )

    return client