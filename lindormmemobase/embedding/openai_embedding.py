import numpy as np
from typing import Literal
from .utils import get_openai_async_client_instance
from ..config import LOG

async def openai_embedding(
    model: str, texts: list[str], phase: Literal["query", "document"] = "document", config=None
) -> np.ndarray:
    openai_async_client = get_openai_async_client_instance(config)
    response = await openai_async_client.embeddings.create(
        model=model, input=texts, encoding_format="float"
    )

    prompt_tokens = getattr(response.usage, "prompt_tokens", None)
    total_tokens = getattr(response.usage, "total_tokens", None)
    LOG.info(f"OpenAI embedding, {model}, {phase}, {prompt_tokens}/{total_tokens}")
    return np.array([dp.embedding for dp in response.data])


async def openai_embedding(
        model: str, texts: list[str], phase: Literal["query", "document"] = "document", config=None
) -> np.ndarray:
    openai_async_client = get_openai_async_client_instance(config)

    # Batch size limit for this API
    MAX_BATCH_SIZE = 10
    all_embeddings = []
    total_prompt_tokens = 0
    total_tokens = 0
    # Process texts in batches
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[i:i + MAX_BATCH_SIZE]
        response = await openai_async_client.embeddings.create(
            model=model, input=batch, encoding_format="float"
        )
        prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
        batch_total_tokens = getattr(response.usage, "total_tokens", 0)
        total_prompt_tokens += prompt_tokens
        total_tokens += batch_total_tokens
        all_embeddings.extend([dp.embedding for dp in response.data])
    LOG.info(f"OpenAI embedding, {model}, {phase}, {total_prompt_tokens}/{total_tokens}")
    return np.array(all_embeddings)
