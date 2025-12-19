from typing import List, Optional
from .utils import get_lindormai_rerank_async_client_instance
from .openai_rerank import RerankResult
from lindormmemobase.config import LOG


async def lindormai_rerank(
    model: str,
    query: str,
    documents: List[str],
    top_n: int = None,
    config=None,
    instruct: Optional[str] = None,
    return_documents: bool = False
) -> List[RerankResult]:
    """
    LindormAI rerank wrapper using DashScope-compatible format.
    
    Args:
        model: Model name
        query: Query text
        documents: List of documents to rerank
        top_n: Number of top results to return
        config: Configuration object
        instruct: Optional custom ranking task instruction
        return_documents: Whether to return document text in response
    
    Returns:
        List of RerankResult objects sorted by relevance score
    """
    client = get_lindormai_rerank_async_client_instance(config)
    
    # Build request body using DashScope format
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
        # LindormAI endpoint (assuming it follows DashScope-like path)
        response = await client.post(
            "dashscope/api/v1/services/rerank/text-rerank/text-rerank",
            json=request_body
        )
        response.raise_for_status()
        data = response.json()
        
        # Check for error response
        if "code" in data and data["code"]:
            error_msg = data.get("message", "Unknown error")
            raise Exception(f"LindormAI API error [{data['code']}]: {error_msg}")
        
        # Parse response using DashScope format
        # Response structure: {"output": {"results": [...]}, "usage": {...}, "request_id": "..."}
        output = data.get("output", {})
        results_data = output.get("results", [])
        
        results = []
        for item in results_data:
            idx = item["index"]
            score = item.get("relevance_score", 0.0)
            
            # If return_documents is True, get document text from response
            # Otherwise, use the original documents array
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
            f"LindormAI rerank: model={model}, {len(documents)} docs, "
            f"top_n={top_n}, returned {len(results)} results"
        )
        return results
        
    except Exception as e:
        LOG.error(f"Error in LindormAI rerank: {e}")
        raise
    finally:
        await client.aclose()
