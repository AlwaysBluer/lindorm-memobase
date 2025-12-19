from typing import List
from traceback import format_exc

from lindormmemobase.config import LOG
from lindormmemobase.utils.errors import RerankError

from .openai_rerank import openai_rerank, RerankResult
from .lindormai_rerank import lindormai_rerank
from .dashscope_rerank import dashscope_rerank


FACTORIES = {
    "openai": openai_rerank,
    "lindormai": lindormai_rerank,
    "dashscope": dashscope_rerank
}


async def get_rerank(
    query: str,
    documents: List[str],
    model: str = None,
    top_n: int = None,
    config=None,
) -> List[RerankResult]:
    if config is None:
        raise ValueError("config parameter is required")
    
    assert (
        config.rerank_provider in FACTORIES
    ), f"Unsupported rerank provider: {config.rerank_provider}"
    
    model = model or config.rerank_model
    try:
        results = await FACTORIES[config.rerank_provider](
            model, query, documents, top_n, config
        )
        return results
    except Exception as e:
        LOG.error(f"Error in get_rerank: {e} {format_exc()}")
        raise RerankError(f"Error in get_rerank: {e}") from e
