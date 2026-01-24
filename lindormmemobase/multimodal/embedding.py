from typing import Union, List
import json
import gzip
from httpx import AsyncClient, DecodingError, HTTPStatusError
from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import EmbeddingError
from lindormmemobase.models.enums import MultimodalInputType


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
    input_type: Union[str, MultimodalInputType],
    content: str,
    model: str = None,
    config=None,
) -> List[float]:
    if config is None:
        raise ValueError("config parameter is required")

    # Convert string to enum for backward compatibility
    if isinstance(input_type, str):
        input_type = MultimodalInputType(input_type)

    provider = config.multimodal_embedding_provider
    model = model or config.multimodal_embedding_model

    if provider == "lindormai":
        base_url = _get_multimodal_base_url(config)
        if not base_url:
            raise EmbeddingError("multimodal_embedding_base_url is required for lindormai provider")
        headers = {
            "x-ld-ak": config.lindorm_username,
            "x-ld-sk": config.lindorm_password,
            "Accept-Encoding": "identity",  # Disable compression to avoid gzip decode errors
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
                    input_type.value: content
                }
            ]
        },
        "model": model,
    }

    async with AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(endpoint, json=body, headers=headers)
            try:
                response.raise_for_status()
            except HTTPStatusError as e:
                body = e.response.text if e.response is not None else ""
                LOG.error(f"Multimodal embedding HTTP error: {e}")
                if body:
                    LOG.error(f"Multimodal embedding response body: {body[:2000]}")
                raise EmbeddingError(
                    f"Multimodal embedding failed: {e}. Response body: {body[:2000]}"
                ) from e

            # Handle potential gzip decode errors from Lindorm AI proxy
            try:
                data = response.json()
            except DecodingError:
                # Manual fallback for malformed gzip responses
                LOG.warning("Failed to decode response, trying manual gzip decompression")
                raw_content = response.content
                try:
                    # Try manual gzip decompression
                    data = json.loads(gzip.decompress(raw_content).decode("utf-8"))
                except Exception:
                    # If that fails, try parsing as-is
                    data = json.loads(raw_content.decode("utf-8"))

            embedding = data.get("output", {}).get("embeddings", [{}])[0].get("embedding")
            if not embedding:
                raise EmbeddingError("No embedding returned from multimodal embedding API")
            return embedding
        except EmbeddingError:
            raise
        except Exception as e:
            LOG.error(f"Multimodal embedding error: {e}")
            raise EmbeddingError(f"Multimodal embedding failed: {e}") from e
