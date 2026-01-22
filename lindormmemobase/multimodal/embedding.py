from typing import Literal, List
from httpx import AsyncClient
from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import EmbeddingError


def _join_url(base_url: str, path: str) -> str:
    if not base_url:
        return path
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def _get_multimodal_base_url(config) -> str:
    return config.multimodal_embedding_base_url or config.embedding_base_url or config.llm_base_url


async def get_multimodal_embedding(
    input_type: Literal["image", "text"],
    content: str,
    model: str = None,
    config=None,
) -> List[float]:
    if config is None:
        raise ValueError("config parameter is required")
    if input_type not in {"image", "text"}:
        raise ValueError("input_type must be 'image' or 'text'")

    provider = config.multimodal_embedding_provider
    model = model or config.multimodal_embedding_model

    if provider == "lindormai":
        base_url = _get_multimodal_base_url(config)
        if not base_url:
            raise EmbeddingError("multimodal_embedding_base_url is required for lindormai provider")
        headers = {
            "x-ld-ak": config.lindorm_username,
            "x-ld-sk": config.lindorm_password,
        }
        endpoint = _join_url(
            base_url,
            "/dashscope/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
        )
    elif provider == "dashscope":
        base_url = config.multimodal_embedding_base_url or "https://dashscope.aliyuncs.com"
        api_key = config.multimodal_embedding_api_key or config.embedding_api_key or config.llm_api_key
        if not api_key:
            raise EmbeddingError("multimodal_embedding_api_key is required for dashscope provider")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        endpoint = _join_url(
            base_url,
            "/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
        )
    else:
        raise EmbeddingError(f"Unsupported multimodal_embedding_provider: {provider}")

    body = {
        "input": {
            "contents": [
                {
                    input_type: content
                }
            ]
        },
        "model": model,
    }

    async with AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            embedding = data.get("output", {}).get("embeddings", [{}])[0].get("embedding")
            if not embedding:
                raise EmbeddingError("No embedding returned from multimodal embedding API")
            return embedding
        except EmbeddingError:
            raise
        except Exception as e:
            LOG.error(f"Multimodal embedding error: {e}")
            raise EmbeddingError(f"Multimodal embedding failed: {e}") from e
