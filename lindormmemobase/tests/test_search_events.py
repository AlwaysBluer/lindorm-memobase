#!/usr/bin/env python3
"""
Lindorm Search Events Integration Tests

This test suite tests the event search and storage functionality using real
Lindorm Search connections from .env and config.yaml configuration.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any

from lindormmemobase.config import Config
from lindormmemobase.core.search.events import (
    get_user_event_gists,
    search_user_event_gists,
    get_user_event_gists_data,
    pack_latest_chat,
    truncate_event_gists
)
from lindormmemobase.core.storage.events import (
    store_event_with_embedding,
    store_event_gist_with_embedding,
    get_lindorm_search_storage
)
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.models.response import UserEventGistsData


class TestLindormSearchEvents:
    """Test suite for Lindorm Search events using real connections."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        try:
            cls.config = Config.load_config()
        except AssertionError as e:
            # If LLM API key is missing, create a minimal config for testing
            import os
            print(f"⚠️ Config validation failed: {e}")
            print("⚠️ Using test configuration for search functionality")
            
            # Create config with minimal required settings
            cls.config = Config.__new__(Config)  # Skip __post_init__
            
            # Set OpenSearch/Lindorm Search configuration from environment or defaults
            cls.config.opensearch_host = os.getenv("MEMOBASE_OPENSEARCH_HOST", "localhost")
            cls.config.opensearch_port = int(os.getenv("MEMOBASE_OPENSEARCH_PORT", "9200"))
            cls.config.opensearch_username = os.getenv("MEMOBASE_OPENSEARCH_USERNAME")
            cls.config.opensearch_password = os.getenv("MEMOBASE_OPENSEARCH_PASSWORD")
            cls.config.opensearch_use_ssl = os.getenv("MEMOBASE_OPENSEARCH_USE_SSL", "false").lower() == "true"
            cls.config.opensearch_events_index = os.getenv("MEMOBASE_OPENSEARCH_EVENTS_INDEX", "memobase_events_test")
            cls.config.opensearch_event_gists_index = os.getenv("MEMOBASE_OPENSEARCH_EVENT_GISTS_INDEX", "memobase_event_gists_test")
            
            # Set embedding configuration
            cls.config.enable_event_embedding = os.getenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "true").lower() == "true"
            cls.config.embedding_provider = os.getenv("MEMOBASE_EMBEDDING_PROVIDER", "openai")
            cls.config.embedding_api_key = os.getenv("MEMOBASE_EMBEDDING_API_KEY") or os.getenv("MEMOBASE_LLM_API_KEY")
            cls.config.embedding_base_url = os.getenv("MEMOBASE_EMBEDDING_BASE_URL")
            cls.config.embedding_dim = int(os.getenv("MEMOBASE_EMBEDDING_DIM", "1536"))
            cls.config.embedding_model = os.getenv("MEMOBASE_EMBEDDING_MODEL", "text-embedding-3-small")
            
            # Set minimal required fields for other components
            cls.config.llm_api_key = os.getenv("MEMOBASE_LLM_API_KEY", "test-key-for-search-test")
            cls.config.language = "en"
            cls.config.best_llm_model = "gpt-4o-mini"
        
        # Test user and event data
        cls.test_user_id = "test_user_search_events"
        cls.test_event_ids = []  # Keep track of created events for cleanup
        cls.test_gist_ids = []   # Keep track of created gists for cleanup
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        try:
            if cls.test_event_ids or cls.test_gist_ids:
                # Create a new event loop for cleanup if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        print(f"⚠️ Skipping cleanup due to running event loop")
                        return
                except RuntimeError:
                    pass
                
                # Clean up test events and gists by deleting test indices
                storage = get_lindorm_search_storage(cls.config)
                try:
                    storage.client.indices.delete(index=cls.config.opensearch_events_index, ignore=[400, 404])
                    storage.client.indices.delete(index=cls.config.opensearch_event_gists_index, ignore=[400, 404])
                    print(f"✅ Cleaned up test indices")
                except Exception as e:
                    print(f"Cleanup warning: {e}")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_lindorm_connection(self):
        """Test basic connection to Lindorm Search."""
        try:
            storage = get_lindorm_search_storage(self.config)
            # Test connection by checking cluster health
            health = storage.client.cluster.health()
            assert 'status' in health
            print(f"✅ Connected to Lindorm Search successfully, status: {health['status']}")
        except Exception as e:
            pytest.fail(f"Failed to connect to Lindorm Search: {e}")
    
    def test_pack_latest_chat(self):
        """Test packing chat messages into a search query string."""
        messages = [
            OpenAICompatibleMessage(role="user", content="Hello there!"),
            OpenAICompatibleMessage(role="assistant", content="Hi! How can I help you?"),
            OpenAICompatibleMessage(role="user", content="I need help with Python programming"),
            OpenAICompatibleMessage(role="assistant", content="Sure! What specific Python topic?"),
            OpenAICompatibleMessage(role="user", content="How to use async/await?")
        ]
        
        # Test default (last 3 messages)
        result = pack_latest_chat(messages)
        expected_lines = [
            "Hi! How can I help you?",
            "I need help with Python programming", 
            "Sure! What specific Python topic?",
            "How to use async/await?"
        ]
        assert result == "\n".join(expected_lines[-3:])
        
        # Test custom number of messages
        result_2 = pack_latest_chat(messages, chat_num=2)
        assert result_2 == "\n".join(expected_lines[-2:])
        
        print("✅ pack_latest_chat works correctly")
    
    @pytest.mark.asyncio
    async def test_store_event_with_embedding(self):
        """Test storing events with embeddings."""
        event_data = {
            "conversation_id": "test_conv_001",
            "message_count": 5,
            "topic": "Python programming help",
            "summary": "User asked about async/await in Python",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Create a simple embedding vector (would normally come from embedding API)
        embedding = [0.1] * self.config.embedding_dim
        
        result = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event: {result.msg()}"
        event_id = result.data()
        assert isinstance(event_id, str)
        assert len(event_id) > 0
        
        self.test_event_ids.append(event_id)
        print(f"✅ Stored event with ID: {event_id}")
        
        return event_id, event_data, embedding
    
    @pytest.mark.asyncio
    async def test_store_event_gist_with_embedding(self):
        """Test storing event gists with embeddings."""
        # First store an event to reference
        event_result = await self.test_store_event_with_embedding()
        event_id, _, _ = event_result
        
        gist_data = {
            "content": "User learned about Python async/await syntax and best practices",
            "key_points": ["async/await basics", "asyncio library", "coroutines"],
            "sentiment": "positive",
            "importance": 0.8,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Create a simple embedding vector
        embedding = [0.2] * self.config.embedding_dim
        
        result = await store_event_gist_with_embedding(
            user_id=self.test_user_id,
            event_id=event_id,
            gist_data=gist_data,
            embedding=embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event gist: {result.msg()}"
        gist_id = result.data()
        assert isinstance(gist_id, str)
        assert len(gist_id) > 0
        
        self.test_gist_ids.append(gist_id)
        print(f"✅ Stored event gist with ID: {gist_id}")
        
        # Give the index some time to refresh
        await asyncio.sleep(2)
        
        return gist_id, gist_data, embedding
    
    @pytest.mark.asyncio
    async def test_get_user_event_gists_basic(self):
        """Test getting user event gists without vector search."""
        # First store some gists
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        result = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=1  # Recent events only
        )
        
        assert result.ok(), f"Failed to get event gists: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        assert len(gists_data.gists) >= 1, "Should have at least one gist"
        
        # Verify gist structure
        gist = gists_data.gists[0]
        assert 'id' in gist
        assert 'gist_data' in gist
        assert 'created_at' in gist
        assert isinstance(gist['gist_data'], dict)
        
        print(f"✅ Retrieved {len(gists_data.gists)} event gists successfully")
        
    @pytest.mark.asyncio
    async def test_search_user_event_gists_vector(self):
        """Test vector-based search of user event gists."""
        if not self.config.enable_event_embedding or not self.config.embedding_api_key:
            pytest.skip("Vector search requires embedding configuration")
        
        # First store some gists with embeddings
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(3)
        
        search_query = "Python async programming help"
        
        result = await search_user_event_gists(
            user_id=self.test_user_id,
            query=search_query,
            config=self.config,
            topk=5,
            similarity_threshold=0.1,  # Low threshold for testing
            time_range_in_days=1
        )
        
        assert result.ok(), f"Failed to search event gists: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        
        print(f"✅ Vector search returned {len(gists_data.gists)} results")
        
        # If we have results, verify they have similarity scores
        if gists_data.gists:
            for gist in gists_data.gists:
                if 'similarity' in gist:
                    assert isinstance(gist['similarity'], (int, float))
                    print(f"   - Gist similarity: {gist['similarity']:.3f}")
    
    @pytest.mark.asyncio
    async def test_get_user_event_gists_data_integration(self):
        """Test the main integration function for getting event data."""
        # Store test data first
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        # Test with chat messages (should trigger vector search if enabled)
        chat_messages = [
            OpenAICompatibleMessage(role="user", content="I need help with Python"),
            OpenAICompatibleMessage(role="assistant", content="What Python topic?"),
            OpenAICompatibleMessage(role="user", content="async/await patterns")
        ]
        
        result = await get_user_event_gists_data(
            user_id=self.test_user_id,
            chats=chat_messages,
            require_event_summary=True,
            event_similarity_threshold=0.1,
            time_range_in_days=1,
            global_config=self.config
        )
        
        assert result.ok(), f"Failed to get event gists data: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        
        print(f"✅ Integration function returned {len(gists_data.gists)} gists")
        
        # Test without chat messages (should use basic retrieval)
        result_basic = await get_user_event_gists_data(
            user_id=self.test_user_id,
            chats=[],  # Empty chat
            require_event_summary=False,
            event_similarity_threshold=0.5,
            time_range_in_days=1,
            global_config=self.config
        )
        
        assert result_basic.ok(), f"Failed to get event gists data (basic): {result_basic.msg()}"
        print("✅ Basic retrieval (no vector search) works correctly")
    
    @pytest.mark.asyncio
    async def test_truncate_event_gists(self):
        """Test truncating event gists by token count."""
        # Create mock gists data
        gists_data = UserEventGistsData(gists=[
            {
                "id": "gist_1",
                "gist_data": {"content": "Short content"},
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": "gist_2", 
                "gist_data": {"content": "This is a much longer piece of content that contains many more tokens and should be truncated when the limit is low"},
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": "gist_3",
                "gist_data": {"content": "Another piece of content"},
                "created_at": datetime.utcnow().isoformat()
            }
        ])
        
        # Test with no limit (should return all)
        result_no_limit = await truncate_event_gists(gists_data, None)
        assert result_no_limit.ok()
        assert len(result_no_limit.data().gists) == 3
        
        # Test with low token limit (should truncate)
        result_truncated = await truncate_event_gists(gists_data, 10)
        assert result_truncated.ok()
        truncated_gists = result_truncated.data().gists
        assert len(truncated_gists) <= 3
        assert len(truncated_gists) >= 1
        
        print(f"✅ Truncation: {len(gists_data.gists)} → {len(truncated_gists)} gists")
    
    @pytest.mark.asyncio
    async def test_time_range_filtering(self):
        """Test that time range filtering works correctly."""
        # Store a gist
        await self.test_store_event_gist_with_embedding() 
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        # Test with very recent time range (should find results)
        result_recent = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=1  # Last 1 day
        )
        
        assert result_recent.ok()
        recent_count = len(result_recent.data().gists)
        
        # Test with very old time range (should find no results)
        result_old = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=0  # No time range (should be empty)
        )
        
        assert result_old.ok()
        old_count = len(result_old.data().gists)
        
        # Recent should have more or equal results than old
        assert recent_count >= old_count
        print(f"✅ Time filtering: recent={recent_count}, old={old_count}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Test with invalid user ID
        result_invalid = await get_user_event_gists(
            user_id="non_existent_user_12345",
            config=self.config,
            topk=5,
            time_range_in_days=30
        )
        
        # Should succeed but return empty results
        assert result_invalid.ok()
        assert len(result_invalid.data().gists) == 0
        
        # Test store without config
        result_no_config = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data={"test": "data"},
            embedding=[0.1] * 10,
            config=None
        )
        
        # Should fail gracefully
        assert not result_no_config.ok()
        assert "CONFIG_ERROR" in result_no_config.msg() or "Config parameter is required" in result_no_config.msg()
        
        print("✅ Error handling works correctly")
    
    @pytest.mark.asyncio
    async def test_large_embedding_vectors(self):
        """Test handling of large embedding vectors."""
        large_embedding = np.random.random(self.config.embedding_dim).tolist()
        
        event_data = {
            "test": "large_embedding",
            "vector_size": len(large_embedding),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=large_embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event with large embedding: {result.msg()}"
        self.test_event_ids.append(result.data())
        
        print(f"✅ Large embedding vector ({len(large_embedding)}D) handled successfully")


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))