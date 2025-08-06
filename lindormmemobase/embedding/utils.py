from openai import AsyncOpenAI
from httpx import AsyncClient
import numpy as np
from traceback import format_exc

from ..config import LOG
from typing import Literal

from ..utils.promise import Promise
from ..models.response import CODE

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