import numpy as np
from typing import Literal
from .utils import get_lindormai_async_client_instance
from ..config import LOG


async def lindormai_embedding(
        model: str,
        texts: list[str],
        phase: Literal["query", "document"] = "document",
        config=None
) -> np.ndarray:
    """Lindormai Embedding 请求（支持批处理）"""
    lindormai_async_client = get_lindormai_async_client_instance(config)
    MAX_BATCH_SIZE = 10
    all_embeddings = []
    total_prompt_tokens = 0
    total_tokens = 0
    try:
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i:i + MAX_BATCH_SIZE]
            response = await lindormai_async_client.embeddings.create(
                model=model,
                input=batch,
                encoding_format="float"
            )
            total_prompt_tokens += getattr(response.usage, "prompt_tokens", 0)
            total_tokens += getattr(response.usage, "total_tokens", 0)
            all_embeddings.extend([dp.embedding for dp in response.data])

        LOG.info(f"Lindormai embedding, {model}, {phase}, {total_prompt_tokens}/{total_tokens}")
        return np.array(all_embeddings)
    except Exception as e:
        LOG.error(f"Error in Lindormai embedding: {e}")
        raise
    finally:
        await lindormai_async_client.close()
