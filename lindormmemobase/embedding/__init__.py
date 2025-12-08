from typing import Literal
import numpy as np
from traceback import format_exc

from ..config import LOG
from ..utils.errors import EmbeddingError

from .openai_embedding import openai_embedding
from .jina_embedding import jina_embedding
from .lindormai_embedding import lindormai_embedding


FACTORIES = {
    "openai": openai_embedding,
    "jina": jina_embedding,
    "lindormai": lindormai_embedding
}

async def get_embedding(
    texts: list[str],
    phase: Literal["query", "document"] = "document",
    model: str = None,
    config=None,
) -> np.ndarray:
    if config is None:
        raise ValueError("config parameter is required")
    
    assert (
        config.embedding_provider in FACTORIES
    ), f"Unsupported embedding provider: {config.embedding_provider}"
    
    model = model or config.embedding_model
    try:
        results = await FACTORIES[config.embedding_provider](model, texts, phase, config)
        return results
    except Exception as e:
        LOG.error(f"Error in get_embedding: {e} {format_exc()}")
        raise EmbeddingError(f"Error in get_embedding: {e}") from e
