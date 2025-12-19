from typing import List, Optional
from httpx import AsyncClient
from lindormmemobase.config import LOG
from .openai_rerank import RerankResult


async def dashscope_rerank(
    model: str,
    query: str,
    documents: List[str],
    top_n: int = None,
    config=None,
    instruct: Optional[str] = None,
    return_documents: bool = False
) -> List[RerankResult]:
    """
    Call DashScope text rerank API.
    
    Args:
        model: Model name (e.g., "qwen3-rerank", "gte-rerank-v2")
        query: Query text
        documents: List of documents to rerank
        top_n: Number of top results to return (default: all)
        config: Configuration object containing rerank_api_key and rerank_base_url
        instruct: Optional custom ranking task instruction (only works with qwen3-rerank)
                 Examples:
                 - "Given a web search query, retrieve relevant passages that answer the query." (default)
                 - "Retrieve semantically similar text."
        return_documents: Whether to return document text in response (default: False)
    
    Returns:
        List of RerankResult objects sorted by relevance score (high to low)
    """
    if config is None:
        raise ValueError("config parameter is required")
    
    # DashScope uses Authorization: Bearer <API_KEY>
    api_key = config.rerank_api_key
    if api_key is None:
        raise ValueError("rerank_api_key is required for DashScope rerank")
    
    # DashScope base URL should be like: https://dashscope.aliyuncs.com
    base_url = config.rerank_base_url or "https://dashscope.aliyuncs.com"
    
    # Create HTTP client
    client = AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )
    
    # Build request body according to DashScope API spec
    request_body = {
        "model": model,
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {}
    }
    
    # Add optional parameters
    if top_n is not None:
        request_body["parameters"]["top_n"] = top_n
    
    if return_documents:
        request_body["parameters"]["return_documents"] = return_documents
    
    if instruct is not None:
        request_body["parameters"]["instruct"] = instruct
    
    try:
        # DashScope rerank endpoint
        response = await client.post(
            "/api/v1/services/rerank/text-rerank/text-rerank",
            json=request_body
        )
        response.raise_for_status()
        data = response.json()
        
        # Check for error response
        if "code" in data and data["code"]:
            error_msg = data.get("message", "Unknown error")
            raise Exception(f"DashScope API error [{data['code']}]: {error_msg}")
        
        # Parse response according to DashScope format
        # Response structure: {"output": {"results": [...]}, "usage": {...}, "request_id": "..."}
        output = data.get("output", {})
        results_data = output.get("results", [])
        
        results = []
        for item in results_data:
            idx = item["index"]
            score = item.get("relevance_score", 0.0)
            
            # If return_documents is True, DashScope returns document text in response
            # Otherwise, we need to get it from the original documents array
            if "document" in item and "text" in item["document"]:
                doc_text = item["document"]["text"]
            else:
                doc_text = documents[idx]
            
            results.append(RerankResult(
                index=idx,
                score=score,
                document=doc_text
            ))
        
        LOG.debug(
            f"DashScope rerank: model={model}, {len(documents)} docs, "
            f"top_n={top_n}, returned {len(results)} results"
        )
        
        return results
        
    except Exception as e:
        LOG.error(f"Error in DashScope rerank: {e}")
        raise
    finally:
        await client.aclose()
