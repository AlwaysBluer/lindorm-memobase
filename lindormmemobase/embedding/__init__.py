from typing import Literal
import numpy as np
from traceback import format_exc

from ..config import LOG
from ..utils.promise import Promise

from ..models.response import CODE

from .openai_embedding import openai_embedding
from .jina_embedding import jina_embedding


FACTORIES = {"openai": openai_embedding, "jina": jina_embedding}

async def get_embedding(
    texts: list[str],
    phase: Literal["query", "document"] = "document",
    model: str = None,
    config=None,
) -> Promise[np.ndarray]:
    if config is None:
        raise ValueError("config parameter is required")
    
    assert (
        config.embedding_provider in FACTORIES
    ), f"Unsupported embedding provider: {config.embedding_provider}"
    
    model = model or config.embedding_model
    try:
        results = await FACTORIES[config.embedding_provider](model, texts, phase, config)
    except Exception as e:
        LOG.error(f"Error in get_embedding: {e} {format_exc()}")
        return Promise.reject(CODE.SERVICE_UNAVAILABLE, f"Error in get_embedding: {e}")

    return Promise.resolve(results)
