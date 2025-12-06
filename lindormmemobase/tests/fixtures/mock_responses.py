"""
Mock LLM and embedding responses for testing.

Provides predefined responses that simulate real LLM and embedding API outputs.
"""

import json
from typing import Dict, Any, List


# ==================== Mock LLM Responses ====================

MOCK_EXTRACT_PROFILE_RESPONSE = """
{
    "user_profile_topics": [
        {
            "topic": "travel",
            "sub_topic": "destinations",
            "profile": "User is planning a trip to Japan in spring (March/April). Interested in visiting Tokyo, Kyoto, and Osaka."
        },
        {
            "topic": "food",
            "sub_topic": "preferences",
            "profile": "User loves Japanese cuisine, particularly ramen and sushi. Wants to try authentic kaiseki dining."
        }
    ]
}
"""

MOCK_EXTRACT_PROFILE_CHINESE_RESPONSE = """
{
    "user_profile_topics": [
        {
            "topic": "语言",
            "sub_topic": "技能",
            "profile": "用户能流利地说英语和中文。"
        },
        {
            "topic": "语言",
            "sub_topic": "学习",
            "profile": "用户在北京生活了3年学习中文。"
        }
    ]
}
"""

MOCK_MERGE_PROFILE_RESPONSE = """
{
    "merged_profile": "User is planning a spring trip to Japan (March/April) to visit Tokyo, Kyoto, and Osaka, with particular interest in experiencing Japanese cuisine including ramen, sushi, and kaiseki dining."
}
"""

MOCK_ORGANIZE_PROFILE_RESPONSE = """
{
    "organized_profiles": [
        {
            "topic": "travel",
            "sub_topic": "destinations",
            "profile": "User plans to visit Japan in spring (March/April), focusing on Tokyo, Kyoto, and Osaka."
        },
        {
            "topic": "food",
            "sub_topic": "japanese",
            "profile": "User enjoys Japanese cuisine: ramen, sushi, and kaiseki."
        }
    ]
}
"""

MOCK_EVENT_SUMMARY_RESPONSE = """
{
    "event_summary": "User discussed plans for a spring trip to Japan, expressing interest in visiting major cities and experiencing authentic Japanese cuisine."
}
"""

MOCK_ENTRY_SUMMARY_RESPONSE = """
{
    "summary": "User is planning a spring trip to Japan with focus on food and culture."
}
"""

MOCK_PICK_RELATED_PROFILES_RESPONSE = """
{
    "related_profile_ids": ["profile_001", "profile_002", "profile_005"]
}
"""

MOCK_CONTEXT_PACK_RESPONSE = """
{
    "context": "Based on your interest in Japan travel and Japanese food, here are relevant memories: You're planning a spring trip to Tokyo, Kyoto, and Osaka. You particularly enjoy ramen and sushi."
}
"""


# ==================== Mock Embedding Responses ====================

def create_mock_embedding_vector(dimension: int = 1536, seed: int = 0) -> List[float]:
    """
    Create a deterministic mock embedding vector.
    
    Args:
        dimension: Vector dimension
        seed: Seed for reproducibility
        
    Returns:
        List of floats representing the embedding vector
    """
    import random
    random.seed(seed)
    return [random.random() for _ in range(dimension)]


def create_mock_embeddings_batch(texts: List[str], dimension: int = 1536) -> List[List[float]]:
    """
    Create mock embeddings for a batch of texts.
    
    Each text gets a unique but deterministic embedding based on its hash.
    
    Args:
        texts: List of text strings
        dimension: Vector dimension
        
    Returns:
        List of embedding vectors
    """
    embeddings = []
    for text in texts:
        seed = hash(text) % (2**31)
        embeddings.append(create_mock_embedding_vector(dimension, seed))
    return embeddings


# Common mock embeddings for testing
MOCK_EMBEDDING_TRAVEL = create_mock_embedding_vector(1536, 1001)
MOCK_EMBEDDING_FOOD = create_mock_embedding_vector(1536, 1002)
MOCK_EMBEDDING_WORK = create_mock_embedding_vector(1536, 1003)
MOCK_EMBEDDING_HOBBY = create_mock_embedding_vector(1536, 1004)


# ==================== Mock Search Responses ====================

def create_mock_search_result(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Create a mock search result from OpenSearch/Lindorm Search.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Dictionary mimicking OpenSearch response format
    """
    hits = []
    for i in range(num_results):
        hits.append({
            "_index": "memobase_event_gists",
            "_id": f"event_{i}",
            "_score": 0.9 - (i * 0.1),
            "_source": {
                "user_id": "test_user",
                "content": f"Event content related to {query} - item {i}",
                "embedding": create_mock_embedding_vector(1536, i),
                "created_at": "2024-12-01T10:00:00Z",
                "updated_at": "2024-12-01T10:00:00Z",
            }
        })
    
    return {
        "hits": {
            "total": {"value": num_results},
            "max_score": 0.9,
            "hits": hits
        }
    }


# ==================== Mock Profile Data Responses ====================

MOCK_PROFILE_DATA_RESPONSE = {
    "profiles": [
        {
            "user_id": "test_user",
            "project_id": "test_project",
            "profile_id": "profile_001",
            "content": "User is planning a trip to Japan.",
            "attributes": {"topic": "travel", "sub_topic": "destinations"},
            "created_at": "2024-12-01T10:00:00",
            "updated_at": "2024-12-01T10:00:00",
        },
        {
            "user_id": "test_user",
            "project_id": "test_project",
            "profile_id": "profile_002",
            "content": "User loves Japanese food.",
            "attributes": {"topic": "food", "sub_topic": "preferences"},
            "created_at": "2024-12-01T10:00:00",
            "updated_at": "2024-12-01T10:00:00",
        }
    ]
}


# ==================== Helper Functions ====================

def parse_mock_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parse mock LLM response JSON.
    
    Args:
        response_text: JSON string response
        
    Returns:
        Parsed dictionary
    """
    return json.loads(response_text)


def create_streaming_chunks(text: str, chunk_size: int = 10) -> List[str]:
    """
    Split text into chunks for simulating streaming responses.
    
    Args:
        text: Text to split
        chunk_size: Size of each chunk
        
    Returns:
        List of text chunks
    """
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


# ==================== Error Responses ====================

MOCK_API_ERROR_RATE_LIMIT = {
    "error": {
        "message": "Rate limit exceeded",
        "type": "rate_limit_error",
        "code": "rate_limit_exceeded"
    }
}

MOCK_API_ERROR_INVALID_KEY = {
    "error": {
        "message": "Invalid API key",
        "type": "invalid_request_error",
        "code": "invalid_api_key"
    }
}

MOCK_API_ERROR_TIMEOUT = {
    "error": {
        "message": "Request timeout",
        "type": "timeout_error",
        "code": "timeout"
    }
}
