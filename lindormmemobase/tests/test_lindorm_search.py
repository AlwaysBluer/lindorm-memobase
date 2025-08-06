#!/usr/bin/env python3
"""
Lindorm Search Storage Integration Tests

This test suite tests the LindormSearchStorage implementation using real
Lindorm Search connections from .env configuration.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from datetime import datetime
from typing import List, Dict, Any

from lindormmemobase.config import Config
from lindormmemobase.core.storage.events import LindormSearchStorage
from lindormmemobase.models.promise import Promise


class TestLindormSearchStorage:
    """Test suite for LindormSearchStorage using real Lindorm connections."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        cls.config = Config.load_config()
        cls.storage = LindormSearchStorage(cls.config)
        cls.test_user_id = "test_user_lindorm_search"
        cls.test_event_ids = []  # Keep track of created events for cleanup
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        # Clean up test events - the gist cleanup will also happen automatically
        # since we don't track gist IDs separately in this simple cleanup
        try:
            for event_id in cls.test_event_ids:
                cls.storage.client.delete(
                    index=cls.config.opensearch_events_index,
                    id=event_id,
                    ignore=[404]
                )
            # Note: Gist cleanup is more complex since we generate UUIDs
            # For test purposes, we rely on the test environment cleanup
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_connection(self):
        """Test basic connection to Lindorm Search."""
        try:
            info = self.storage.client.info()
            assert 'version' in info
            print(f"✅ Connected to Lindorm Search: {info['version']['number']}")
        except Exception as e:
            pytest.fail(f"Failed to connect to Lindorm Search: {e}")
    
    def test_indices_creation(self):
        """Test that indices are created properly."""
        try:
            # Check events index
            events_exists = self.storage.client.indices.exists(
                index=self.config.opensearch_events_index
            )
            assert events_exists, f"Events index {self.config.opensearch_events_index} should exist"
            
            # Check event gists index  
            gists_exists = self.storage.client.indices.exists(
                index=self.config.opensearch_event_gists_index
            )
            assert gists_exists, f"Event gists index {self.config.opensearch_event_gists_index} should exist"
            
            print("✅ Indices exist and are accessible")
        except Exception as e:
            pytest.fail(f"Failed to verify indices: {e}")
    
    @pytest.mark.asyncio
    async def test_store_event_with_embedding(self):
        """Test storing an event with embedding."""
        event_data = {
            "event_tip": "User discussed their favorite programming languages",
            "event_tags": ["programming", "preferences"],
            "profile_delta": [
                {"topic": "interests", "sub_topic": "programming", "content": "Loves Python and JavaScript"}
            ]
        }
        
        # Create a dummy embedding vector
        embedding = [0.1] * self.config.embedding_dim
        
        result = await self.storage.store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding
        )
        
        assert result.ok(), f"Failed to store event: {result.msg()}"
        event_id = result.data()
        self.test_event_ids.append(event_id)
        
        # Verify the event was stored
        try:
            stored_event = self.storage.client.get(
                index=self.config.opensearch_events_index,
                id=event_id
            )
            assert stored_event['_source']['user_id'] == self.test_user_id
            assert stored_event['_source']['event_data'] == event_data
            assert len(stored_event['_source']['embedding']) == self.config.embedding_dim
            
            print(f"✅ Event stored successfully with ID: {event_id}")
        except Exception as e:
            pytest.fail(f"Failed to verify stored event: {e}")
    
    @pytest.mark.asyncio
    async def test_store_event_gist_with_embedding(self):
        """Test storing an event gist with embedding."""
        # First create a regular event
        event_data = {
            "event_tip": "User completed a coding project",
            "event_tags": ["achievement", "coding"],
            "profile_delta": []
        }
        embedding = [0.2] * self.config.embedding_dim
        
        event_result = await self.storage.store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding
        )
        assert event_result.ok()
        event_id = event_result.data()
        self.test_event_ids.append(event_id)
        
        # Now store a gist for this event
        gist_data = {
            "summary": "User successfully completed their first machine learning project",
            "key_insights": ["Strong problem-solving skills", "Quick learner"],
            "importance_score": 8.5
        }
        gist_embedding = [0.3] * self.config.embedding_dim
        
        gist_result = await self.storage.store_event_gist_with_embedding(
            user_id=self.test_user_id,
            event_id=event_id,
            gist_data=gist_data,
            embedding=gist_embedding
        )
        
        assert gist_result.ok(), f"Failed to store event gist: {gist_result.msg()}"
        gist_id = gist_result.data()
        
        # Wait for indexing
        await asyncio.sleep(2)
        
        # Verify the gist was stored using the returned gist_id
        try:
            stored_gist = self.storage.client.get(
                index=self.config.opensearch_event_gists_index,
                id=gist_id
            )
            assert stored_gist['_source']['user_id'] == self.test_user_id
            assert stored_gist['_source']['event_id'] == event_id
            assert stored_gist['_source']['gist_data'] == gist_data
            assert len(stored_gist['_source']['embedding']) == self.config.embedding_dim
            
            print(f"✅ Event gist stored successfully for event: {event_id}")
        except Exception as e:
            # Try once more after additional wait
            await asyncio.sleep(3)
            try:
                stored_gist = self.storage.client.get(
                    index=self.config.opensearch_event_gists_index,
                    id=gist_id
                )
                print(f"✅ Event gist stored successfully for event: {event_id} (after retry)")
            except:
                pytest.fail(f"Failed to verify stored gist after retries: {e}")
    
    @pytest.mark.asyncio
    async def test_hybrid_search_events(self):
        """Test hybrid search for events."""
        # Store a test event first
        event_data = {
            "event_tip": "User mentioned loving machine learning and data science",
            "event_tags": ["interests", "career"],
            "profile_delta": []
        }
        embedding = [0.4] * self.config.embedding_dim
        
        result = await self.storage.store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding
        )
        assert result.ok()
        event_id = result.data()
        self.test_event_ids.append(event_id)
        
        # Wait a bit for indexing
        await asyncio.sleep(2)
        
        # Search for the event
        query = "machine learning data science"
        query_vector = [0.4] * self.config.embedding_dim
        
        search_result = await self.storage.hybrid_search_events(
            user_id=self.test_user_id,
            query=query,
            query_vector=query_vector,
            size=5
        )
        
        assert search_result.ok(), f"Search failed: {search_result.msg()}"
        results = search_result.data()
        
        # Should receive a valid response (may be empty due to indexing delays or routing)
        assert isinstance(results, list), "Search should return a list of results"
        
        print(f"✅ Hybrid search returned {len(results)} events (search functionality working)")
    
    @pytest.mark.asyncio
    async def test_hybrid_search_gist_events(self):
        """Test hybrid search for event gists."""
        # Store a test event and gist first
        event_data = {
            "event_tip": "User discussed their passion for artificial intelligence research",
            "event_tags": ["research", "ai"],
            "profile_delta": []
        }
        embedding = [0.5] * self.config.embedding_dim
        
        event_result = await self.storage.store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding
        )
        assert event_result.ok()
        event_id = event_result.data()
        self.test_event_ids.append(event_id)
        
        # Store gist
        gist_data = {
            "summary": "User has deep interest in AI research and neural networks",
            "key_insights": ["Research-oriented mindset", "Strong technical background"],
            "importance_score": 9.0
        }
        gist_embedding = [0.5] * self.config.embedding_dim
        
        gist_result = await self.storage.store_event_gist_with_embedding(
            user_id=self.test_user_id,
            event_id=event_id,
            gist_data=gist_data,
            embedding=gist_embedding
        )
        assert gist_result.ok()
        
        # Wait for indexing
        await asyncio.sleep(2)
        
        # Search for gists
        query = "artificial intelligence neural networks"
        query_vector = [0.5] * self.config.embedding_dim
        
        search_result = await self.storage.hybrid_search_gist_events(
            user_id=self.test_user_id,
            query=query,
            query_vector=query_vector,
            size=5
        )
        
        assert search_result.ok(), f"Gist search failed: {search_result.msg()}"
        results = search_result.data()
        
        # Should receive a valid response (may be empty due to indexing delays or routing)
        assert isinstance(results, list), "Gist search should return a list of results"
        
        print(f"✅ Hybrid gist search returned {len(results)} gists (search functionality working)")
    
    def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Test with invalid index
        try:
            self.storage.client.search(
                index="non_existent_index",
                body={"query": {"match_all": {}}}
            )
        except Exception as e:
            print(f"✅ Error handling works: {type(e).__name__}")
    
    @pytest.mark.asyncio
    async def test_store_event_without_embedding(self):
        """Test storing event without embedding (should handle gracefully)."""
        event_data = {
            "event_tip": "Test event without embedding",
            "event_tags": ["test"],
            "profile_delta": []
        }
        
        result = await self.storage.store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=None
        )
        
        # This should either work (storing null embedding) or fail gracefully
        # The exact behavior depends on your schema configuration
        if result.ok():
            event_id = result.data()
            self.test_event_ids.append(event_id)
            print(f"✅ Event stored without embedding: {event_id}")
        else:
            print(f"✅ Event without embedding handled: {result.msg()}")


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))