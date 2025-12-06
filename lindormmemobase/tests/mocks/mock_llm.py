"""
Mock LLM client for testing.

Provides a mock implementation of LLM clients that returns predefined responses
without making actual API calls.
"""

import asyncio
from typing import Optional, Dict, Any, List, AsyncIterator
from unittest.mock import AsyncMock

from ..fixtures.mock_responses import (
    MOCK_EXTRACT_PROFILE_RESPONSE,
    MOCK_MERGE_PROFILE_RESPONSE,
    MOCK_ORGANIZE_PROFILE_RESPONSE,
    MOCK_EVENT_SUMMARY_RESPONSE,
    MOCK_ENTRY_SUMMARY_RESPONSE,
    create_streaming_chunks,
)


class MockLLMClient:
    """
    Mock LLM client that returns predefined responses.
    
    This client can be configured to return specific responses based on
    prompt patterns or to simulate errors.
    """
    
    def __init__(
        self,
        default_response: str = "Mock LLM response",
        simulate_error: bool = False,
        error_message: str = "Mock API error",
        response_delay: float = 0.0
    ):
        """
        Initialize mock LLM client.
        
        Args:
            default_response: Default response text
            simulate_error: Whether to simulate API errors
            error_message: Error message to raise
            response_delay: Delay in seconds before returning response
        """
        self.default_response = default_response
        self.simulate_error = simulate_error
        self.error_message = error_message
        self.response_delay = response_delay
        self.call_count = 0
        self.last_messages = None
        self.last_model = None
        
        # Map prompt keywords to specific responses
        self.response_map = {
            "extract": MOCK_EXTRACT_PROFILE_RESPONSE,
            "merge": MOCK_MERGE_PROFILE_RESPONSE,
            "organize": MOCK_ORGANIZE_PROFILE_RESPONSE,
            "event": MOCK_EVENT_SUMMARY_RESPONSE,
            "summary": MOCK_ENTRY_SUMMARY_RESPONSE,
        }
    
    async def create_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mock completion method.
        
        Returns predefined response based on message content patterns.
        """
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)
        
        if self.simulate_error:
            raise Exception(self.error_message)
        
        # Determine response based on message content
        response_text = self.default_response
        if messages:
            last_message = messages[-1].get("content", "").lower()
            for keyword, response in self.response_map.items():
                if keyword in last_message:
                    response_text = response
                    break
        
        return {
            "id": f"mock-completion-{self.call_count}",
            "object": "chat.completion",
            "created": 1234567890,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
    
    async def create_streaming_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Mock streaming completion method.
        
        Yields chunks of the response text.
        """
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        
        if self.simulate_error:
            raise Exception(self.error_message)
        
        # Determine response
        response_text = self.default_response
        if messages:
            last_message = messages[-1].get("content", "").lower()
            for keyword, response in self.response_map.items():
                if keyword in last_message:
                    response_text = response
                    break
        
        # Stream in chunks
        chunks = create_streaming_chunks(response_text, chunk_size=20)
        for i, chunk in enumerate(chunks):
            if self.response_delay > 0:
                await asyncio.sleep(self.response_delay)
            
            yield {
                "id": f"mock-stream-{self.call_count}",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk} if i > 0 else {"role": "assistant", "content": chunk},
                        "finish_reason": "stop" if i == len(chunks) - 1 else None
                    }
                ]
            }
    
    def reset_call_count(self):
        """Reset the call counter."""
        self.call_count = 0
        self.last_messages = None
        self.last_model = None
    
    def set_response_for_keyword(self, keyword: str, response: str):
        """Set a specific response for a keyword pattern."""
        self.response_map[keyword] = response


class MockOpenAIClient(MockLLMClient):
    """
    Mock OpenAI client compatible with openai library interface.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat = MockChatCompletion(self)


class MockChatCompletion:
    """Mock chat completion interface."""
    
    def __init__(self, client: MockLLMClient):
        self.client = client
        self.completions = self
    
    async def create(self, messages: List[Dict], model: str, **kwargs):
        """Create a completion."""
        if kwargs.get("stream", False):
            async def stream_wrapper():
                async for chunk in self.client.create_streaming_completion(messages, model, **kwargs):
                    yield chunk
            return stream_wrapper()
        else:
            return await self.client.create_completion(messages, model, **kwargs)


def create_mock_llm_client(
    response_type: str = "default",
    simulate_error: bool = False
) -> MockLLMClient:
    """
    Factory function to create configured mock LLM clients.
    
    Args:
        response_type: Type of response ("default", "extract", "merge", etc.)
        simulate_error: Whether to simulate API errors
        
    Returns:
        Configured MockLLMClient instance
    """
    response_map = {
        "default": "Mock LLM response",
        "extract": MOCK_EXTRACT_PROFILE_RESPONSE,
        "merge": MOCK_MERGE_PROFILE_RESPONSE,
        "organize": MOCK_ORGANIZE_PROFILE_RESPONSE,
        "event": MOCK_EVENT_SUMMARY_RESPONSE,
        "summary": MOCK_ENTRY_SUMMARY_RESPONSE,
    }
    
    default_response = response_map.get(response_type, response_map["default"])
    
    return MockLLMClient(
        default_response=default_response,
        simulate_error=simulate_error
    )
