"""
Mock embedding client for testing.

Provides deterministic embeddings without making actual API calls.
"""

import asyncio
from typing import List, Union
from ..fixtures.mock_responses import (
    create_mock_embedding_vector,
    create_mock_embeddings_batch
)


class MockEmbeddingClient:
    """
    Mock embedding client that returns deterministic vectors.
    
    Embeddings are generated based on text hashes, ensuring the same
    text always produces the same embedding vector.
    """
    
    def __init__(
        self,
        dimension: int = 1536,
        simulate_error: bool = False,
        error_message: str = "Mock embedding error",
        response_delay: float = 0.0
    ):
        """
        Initialize mock embedding client.
        
        Args:
            dimension: Embedding vector dimension
            simulate_error: Whether to simulate API errors
            error_message: Error message to raise
            response_delay: Delay in seconds before returning response
        """
        self.dimension = dimension
        self.simulate_error = simulate_error
        self.error_message = error_message
        self.response_delay = response_delay
        self.call_count = 0
        self.last_input = None
    
    async def create_embedding(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-v3"
    ) -> Union[List[float], List[List[float]]]:
        """
        Create embedding(s) for input text.
        
        Args:
            text: Single text string or list of text strings
            model: Model name (ignored in mock)
            
        Returns:
            Single embedding vector or list of embedding vectors
        """
        self.call_count += 1
        self.last_input = text
        
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)
        
        if self.simulate_error:
            raise Exception(self.error_message)
        
        # Handle single text or batch
        if isinstance(text, str):
            seed = hash(text) % (2**31)
            return create_mock_embedding_vector(self.dimension, seed)
        else:
            return create_mock_embeddings_batch(text, self.dimension)
    
    def reset_call_count(self):
        """Reset the call counter."""
        self.call_count = 0
        self.last_input = None


class MockOpenAIEmbedding(MockEmbeddingClient):
    """
    Mock OpenAI embedding client compatible with openai library interface.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embeddings = self
    
    async def create(
        self,
        input: Union[str, List[str]],
        model: str = "text-embedding-3-small",
        **kwargs
    ) -> dict:
        """
        Create embeddings with OpenAI-compatible response format.
        
        Args:
            input: Text or list of texts to embed
            model: Model name
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Dictionary matching OpenAI embeddings API response format
        """
        embeddings = await self.create_embedding(input, model)
        
        # Format as OpenAI response
        if isinstance(input, str):
            embeddings = [embeddings]
            input = [input]
        
        data = []
        for i, embedding in enumerate(embeddings):
            data.append({
                "object": "embedding",
                "index": i,
                "embedding": embedding
            })
        
        return {
            "object": "list",
            "data": data,
            "model": model,
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in input),
                "total_tokens": sum(len(t.split()) for t in input)
            }
        }


class MockJinaEmbedding(MockEmbeddingClient):
    """
    Mock Jina embedding client.
    """
    
    async def create(
        self,
        input: Union[str, List[str]],
        model: str = "jina-embeddings-v3",
        **kwargs
    ) -> dict:
        """Create embeddings with Jina-compatible response format."""
        embeddings = await self.create_embedding(input, model)
        
        if isinstance(input, str):
            embeddings = [embeddings]
            input = [input]
        
        data = []
        for i, embedding in enumerate(embeddings):
            data.append({
                "index": i,
                "embedding": embedding,
                "object": "embedding"
            })
        
        return {
            "model": model,
            "object": "list",
            "usage": {
                "total_tokens": sum(len(t.split()) for t in input),
                "prompt_tokens": sum(len(t.split()) for t in input)
            },
            "data": data
        }


def create_mock_embedding_client(
    provider: str = "openai",
    dimension: int = 1536,
    simulate_error: bool = False
) -> MockEmbeddingClient:
    """
    Factory function to create mock embedding clients.
    
    Args:
        provider: Provider name ("openai", "jina", or "generic")
        dimension: Embedding dimension
        simulate_error: Whether to simulate errors
        
    Returns:
        Configured mock embedding client
    """
    if provider == "openai":
        return MockOpenAIEmbedding(
            dimension=dimension,
            simulate_error=simulate_error
        )
    elif provider == "jina":
        return MockJinaEmbedding(
            dimension=dimension,
            simulate_error=simulate_error
        )
    else:
        return MockEmbeddingClient(
            dimension=dimension,
            simulate_error=simulate_error
        )
