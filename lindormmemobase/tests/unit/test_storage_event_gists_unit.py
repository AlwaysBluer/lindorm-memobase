"""Unit tests for LindormEventGistsStorage class.

These tests validate the EventGists storage layer operations with mocked dependencies,
ensuring isolation from real database connections.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
from lindormmemobase.core.storage.event_gists import LindormEventGistsStorage


@pytest.mark.unit
class TestEventGistsStorageInitialization:
    """Test EventGists storage initialization and configuration."""
    
    def test_pool_name_uniqueness(self, mock_config):
        """Test that EventGists storage has unique pool name."""
        storage = LindormEventGistsStorage(mock_config)
        pool_name = storage._get_pool_name()
        
        assert pool_name == "memobase_event_gists_pool"
        assert "gists" in pool_name.lower()
    
    def test_independent_opensearch_client(self, mock_config):
        """Test EventGists has independent OpenSearch client."""
        storage = LindormEventGistsStorage(mock_config)
        
        assert storage.client is not None
        assert storage.event_gist_index_name == f"{mock_config.lindorm_table_database}.UserEventsGists.srh_idx"
    
    def test_pool_config_parameters(self, mock_config):
        """Test pool configuration has correct parameters."""
        storage = LindormEventGistsStorage(mock_config)
        pool_config = storage._get_pool_config()
        
        assert pool_config['host'] == mock_config.lindorm_table_host
        assert pool_config['port'] == mock_config.lindorm_table_port
        assert pool_config['database'] == mock_config.lindorm_table_database


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventGistsStorageOperations:
    """Test CRUD operations for EventGists storage."""
    
    async def test_store_single_gist_with_embedding(
        self, mock_event_gists_storage, sample_event_gist_text, mock_embedding_vector
    ):
        """Test storing a single event gist with embedding."""
        result = await mock_event_gists_storage.store_event_gist_with_embedding(
            user_id="user_001",
            project_id="proj_001",
            event_id="event_001",
            gist_idx=0,
            gist_text=sample_event_gist_text,
            embedding=mock_embedding_vector
        )
        
        assert result == "event_001"
        # Verify stored in mock
        key = ("user_001", "proj_001", "event_001", 0)
        assert key in mock_event_gists_storage.gists
        assert mock_event_gists_storage.gists[key]['event_gist_data'] == sample_event_gist_text
    
    async def test_store_multiple_gists_per_event(
        self, mock_event_gists_storage
    ):
        """Test storing multiple gists for the same event."""
        event_id = "event_multi"
        
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_multi", "proj", event_id, 0, "First gist"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_multi", "proj", event_id, 1, "Second gist"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_multi", "proj", event_id, 2, "Third gist"
        )
        
        # Verify all three gists stored
        assert ("user_multi", "proj", event_id, 0) in mock_event_gists_storage.gists
        assert ("user_multi", "proj", event_id, 1) in mock_event_gists_storage.gists
        assert ("user_multi", "proj", event_id, 2) in mock_event_gists_storage.gists
    
    async def test_store_gist_without_embedding(
        self, mock_event_gists_storage
    ):
        """Test storing gist without embedding."""
        result = await mock_event_gists_storage.store_event_gist_with_embedding(
            user_id="user_no_emb",
            project_id="proj",
            event_id="event_no_emb",
            gist_idx=0,
            gist_text="No embedding gist",
            embedding=None
        )
        
        assert result == "event_no_emb"
        key = ("user_no_emb", "proj", "event_no_emb", 0)
        assert mock_event_gists_storage.gists[key]['embedding'] is None
    
    async def test_delete_event_gist(
        self, mock_event_gists_storage
    ):
        """Test deleting all gists for an event."""
        # Store multiple gists for same event
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_del", "proj_del", "event_del", 0, "Gist 1"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_del", "proj_del", "event_del", 1, "Gist 2"
        )
        
        # Delete all gists for this event
        result = await mock_event_gists_storage.delete_event_gist(
            user_id="user_del",
            project_id="proj_del",
            event_id="event_del"
        )
        
        assert result == "event_del"
        assert ("user_del", "proj_del", "event_del", 0) not in mock_event_gists_storage.gists
        assert ("user_del", "proj_del", "event_del", 1) not in mock_event_gists_storage.gists
    
    async def test_delete_event_gists_by_event_id_returns_count(
        self, mock_event_gists_storage
    ):
        """Test cascade deletion returns count of deleted gists."""
        # Store 3 gists for same event
        for idx in range(3):
            await mock_event_gists_storage.store_event_gist_with_embedding(
                "user_count", "proj", "event_cascade", idx, f"Gist {idx}"
            )
        
        count = await mock_event_gists_storage.delete_event_gists_by_event_id(
            user_id="user_count",
            project_id="proj",
            event_id="event_cascade"
        )
        
        assert count == 3
    
    async def test_get_event_gists_by_filter_with_project_id(
        self, mock_event_gists_storage
    ):
        """Test retrieving gists filtered by project_id."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_filter", "proj_1", "event_1", 0, "Gist in proj_1"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_filter", "proj_2", "event_2", 0, "Gist in proj_2"
        )
        
        results = await mock_event_gists_storage.get_event_gists_by_filter(
            user_id="user_filter",
            project_id="proj_1"
        )
        
        assert len(results) == 1
        assert results[0]['gist_data']['content'] == "Gist in proj_1"
    
    async def test_get_event_gists_by_filter_without_project_id(
        self, mock_event_gists_storage
    ):
        """Test retrieving all gists for user across projects."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_all", "proj_1", "event_1", 0, "Gist 1"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_all", "proj_2", "event_2", 0, "Gist 2"
        )
        
        results = await mock_event_gists_storage.get_event_gists_by_filter(
            user_id="user_all",
            project_id=None
        )
        
        assert len(results) == 2
    
    async def test_get_event_gists_composite_id_format(
        self, mock_event_gists_storage
    ):
        """Test that composite ID is formatted as event_id_gist_idx."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_id", "proj", "event_123", 5, "Test gist"
        )
        
        results = await mock_event_gists_storage.get_event_gists_by_filter(
            user_id="user_id",
            project_id="proj"
        )
        
        assert len(results) == 1
        assert results[0]['id'] == "event_123_5"
    
    async def test_get_event_gists_respects_time_range(
        self, mock_event_gists_storage
    ):
        """Test time range filtering."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_time", "proj", "event_old", 0, "Old gist"
        )
        
        # Set old timestamp
        key = ("user_time", "proj", "event_old", 0)
        old_time = datetime.now(timezone.utc) - timedelta(days=30)
        mock_event_gists_storage.gists[key]['created_at'] = old_time
        
        results = await mock_event_gists_storage.get_event_gists_by_filter(
            user_id="user_time",
            project_id="proj",
            time_range_in_days=21
        )
        
        assert len(results) == 0
    
    async def test_get_event_gists_respects_limit(
        self, mock_event_gists_storage
    ):
        """Test result limit."""
        for i in range(10):
            await mock_event_gists_storage.store_event_gist_with_embedding(
                "user_limit", "proj", f"event_{i}", 0, f"Gist {i}"
            )
        
        results = await mock_event_gists_storage.get_event_gists_by_filter(
            user_id="user_limit",
            project_id="proj",
            limit=5
        )
        
        assert len(results) == 5
    
    async def test_reset_with_user_and_project(
        self, mock_event_gists_storage
    ):
        """Test reset with user_id and project_id filters."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_reset", "proj_a", "event_1", 0, "Gist A"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_reset", "proj_b", "event_2", 0, "Gist B"
        )
        
        count = await mock_event_gists_storage.reset("user_reset", "proj_a")
        
        assert count == 1
        assert ("user_reset", "proj_a", "event_1", 0) not in mock_event_gists_storage.gists
        assert ("user_reset", "proj_b", "event_2", 0) in mock_event_gists_storage.gists
    
    async def test_reset_with_user_only(
        self, mock_event_gists_storage
    ):
        """Test reset with only user_id."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_reset_all", "proj_1", "event_1", 0, "Gist 1"
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_reset_all", "proj_2", "event_2", 0, "Gist 2"
        )
        
        count = await mock_event_gists_storage.reset("user_reset_all", None)
        
        assert count == 2
        assert len(mock_event_gists_storage.gists) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventGistsHybridSearch:
    """Test hybrid search functionality for EventGists."""
    
    async def test_hybrid_search_with_project_id_filter(
        self, mock_event_gists_storage
    ):
        """Test hybrid search filters by project_id."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_search", "proj_1", "event_1", 0, "travel to Japan", [0.1] * 1536
        )
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_search", "proj_2", "event_2", 0, "travel to Korea", [0.2] * 1536
        )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_search",
            query="travel Japan",
            query_vector=[0.15] * 1536,
            project_id="proj_1"
        )
        
        assert len(results) == 1
        assert "event_1" in results[0]['id']
    
    async def test_hybrid_search_gist_data_wrapper(
        self, mock_event_gists_storage
    ):
        """Test that results wrap plain text in gist_data structure."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_wrap", "proj", "event", 0, "Test gist content", [0.1] * 1536
        )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_wrap",
            query="test",
            query_vector=[0.1] * 1536
        )
        
        assert len(results) > 0
        assert 'gist_data' in results[0]
        assert 'content' in results[0]['gist_data']
        assert results[0]['gist_data']['content'] == "Test gist content"
    
    async def test_hybrid_search_similarity_scoring(
        self, mock_event_gists_storage
    ):
        """Test hybrid search returns similarity scores."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_sim", "proj", "event", 0, "planning trip to Japan", [0.1] * 1536
        )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_sim",
            query="trip Japan",
            query_vector=[0.1] * 1536
        )
        
        assert len(results) > 0
        assert 'similarity' in results[0]
        assert 0.0 <= results[0]['similarity'] <= 1.0
    
    async def test_hybrid_search_respects_min_score(
        self, mock_event_gists_storage
    ):
        """Test hybrid search filters by minimum score."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_score", "proj", "event", 0, "completely unrelated", [0.1] * 1536
        )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_score",
            query="travel Japan",
            query_vector=[0.9] * 1536,
            min_score=0.9
        )
        
        assert len(results) == 0
    
    async def test_hybrid_search_respects_size_limit(
        self, mock_event_gists_storage
    ):
        """Test hybrid search respects size parameter."""
        for i in range(10):
            await mock_event_gists_storage.store_event_gist_with_embedding(
                "user_size", "proj", f"event_{i}", 0, "travel to Japan", [0.1] * 1536
            )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_size",
            query="travel Japan",
            query_vector=[0.1] * 1536,
            size=5
        )
        
        assert len(results) == 5
    
    async def test_hybrid_search_composite_id_in_results(
        self, mock_event_gists_storage
    ):
        """Test that search results include composite IDs."""
        await mock_event_gists_storage.store_event_gist_with_embedding(
            "user_id", "proj", "event_abc", 3, "test gist", [0.1] * 1536
        )
        
        results = await mock_event_gists_storage.hybrid_search_event_gists(
            user_id="user_id",
            query="test",
            query_vector=[0.1] * 1536
        )
        
        assert len(results) > 0
        assert results[0]['id'] == "event_abc_3"
