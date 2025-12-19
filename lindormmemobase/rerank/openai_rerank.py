from typing import List
from dataclasses import dataclass
from .utils import get_rerank_async_client_instance
from lindormmemobase.config import LOG


@dataclass
class RerankResult:
    index: int
    score: float
    document: str


async def openai_rerank(
    model: str,
    query: str,
    documents: List[str],
    top_n: int = None,
    config=None
) -> List[RerankResult]:
    client = get_rerank_async_client_instance(config)
    
    request_body = {
        "model": model,
        "query": query,
        "documents": documents,
    }
    if top_n is not None:
        request_body["top_n"] = top_n
    
    try:
        response = await client.post("/rerank", json=request_body)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", []):
            idx = item["index"]
            results.append(RerankResult(
                index=idx,
                score=item.get("relevance_score", item.get("score", 0.0)),
                document=documents[idx]
            ))
        
        LOG.debug(f"OpenAI rerank, {model}, {len(documents)} docs, top_n={top_n}")
        return results
    except Exception as e:
        LOG.error(f"Error in OpenAI rerank: {e}")
        raise
