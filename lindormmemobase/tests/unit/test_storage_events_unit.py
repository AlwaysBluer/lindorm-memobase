"""Unit tests for LindormEventsStorage class.

These tests validate the Events storage layer operations with mocked dependencies,
ensuring isolation from real database connections.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
from lindormmemobase.core.storage.events import LindormEventsStorage
from lindormmemobase.utils.errors import StorageError, SearchStorageError


@pytest.mark.unit
class TestEventsStorageInitialization:
    """Test Events storage initialization and configuration."""
    
    def test_pool_name_uniqueness(self, mock_config):
        """Test that Events storage has unique pool name."""
        with patch('lindormmemobase.core.storage.events.StorageManager'):
            storage = LindormEventsStorage(mock_config)
            pool_name = storage._get_pool_name()
            
            assert pool_name == "memobase_events_pool"
            assert "events" in pool_name.lower()
    
    def test_opensearch_client_configuration(self, mock_config):
        """Test OpenSearch client is configured correctly."""
        with patch('lindormmemobase.core.storage.events.StorageManager'):
            storage = LindormEventsStorage(mock_config)
            
            assert storage.client is not None
            assert storage.event_index_name == f"{mock_config.lindorm_table_database}.UserEvents.srh_idx"
    
    def test_pool_config_returns_correct_parameters(self, mock_config):
        """Test pool configuration has correct connection parameters."""
        with patch('lindormmemobase.core.storage.events.StorageManager'):
            storage = LindormEventsStorage(mock_config)
            pool_config = storage._get_pool_config()
            
            assert pool_config['host'] == mock_config.lindorm_table_host
            assert pool_config['port'] == mock_config.lindorm_table_port
            assert pool_config['user'] == mock_config.lindorm_table_username
            assert pool_config['database'] == mock_config.lindorm_table_database


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventsStorageOperations:
    """Test CRUD operations for Events storage."""
    
    async def test_store_event_with_embedding_success(
        self, mock_events_storage, sample_event_data, mock_embedding_vector
    ):
        """Test successfully storing an event with embedding."""
        user_id = "test_user"
        project_id = "test_project"
        event_id = "event_001"
        
        result = await mock_events_storage.store_event_with_embedding(
            user_id=user_id,
            project_id=project_id,
            event_id=event_id,
            event_data=sample_event_data,
            embedding=mock_embedding_vector
        )
        
        assert result == event_id
        # Verify stored in mock storage
        key = (user_id, project_id, event_id)
        assert key in mock_events_storage.events
        assert mock_events_storage.events[key]['event_data'] == sample_event_data
    
    async def test_store_event_without_embedding(
        self, mock_events_storage, sample_event_data
    ):
        """Test storing event without embedding."""
        result = await mock_events_storage.store_event_with_embedding(
            user_id="user_001",
            project_id="proj_001",
            event_id="event_no_emb",
            event_data=sample_event_data,
            embedding=None
        )
        
        assert result == "event_no_emb"
        key = ("user_001", "proj_001", "event_no_emb")
        assert mock_events_storage.events[key]['embedding'] is None
    
    async def test_delete_event_success(self, mock_events_storage, sample_event_data):
        """Test successfully deleting an event."""
        # First store an event
        await mock_events_storage.store_event_with_embedding(
            user_id="user_del",
            project_id="proj_del",
            event_id="event_to_delete",
            event_data=sample_event_data
        )
        
        # Verify it exists
        key = ("user_del", "proj_del", "event_to_delete")
        assert key in mock_events_storage.events
        
        # Delete it
        result = await mock_events_storage.delete_event(
            user_id="user_del",
            project_id="proj_del",
            event_id="event_to_delete"
        )
        
        assert result == "event_to_delete"
        assert key not in mock_events_storage.events
    
    async def test_get_events_by_filter_with_project_id(
        self, mock_events_storage, sample_event_data
    ):
        """Test retrieving events filtered by user_id and project_id."""
        # Store events in different projects
        await mock_events_storage.store_event_with_embedding(
            "user_a", "project_1", "event_1", sample_event_data
        )
        await mock_events_storage.store_event_with_embedding(
            "user_a", "project_2", "event_2", sample_event_data
        )
        
        # Filter by project_1
        results = await mock_events_storage.get_events_by_filter(
            user_id="user_a",
            project_id="project_1"
        )
        
        assert len(results) == 1
        assert results[0]['id'] == "event_1"
    
    async def test_get_events_by_filter_without_project_id(
        self, mock_events_storage, sample_event_data
    ):
        """Test retrieving all events for user across projects."""
        await mock_events_storage.store_event_with_embedding(
            "user_b", "project_1", "event_1", sample_event_data
        )
        await mock_events_storage.store_event_with_embedding(
            "user_b", "project_2", "event_2", sample_event_data
        )
        
        # Get all events for user_b
        results = await mock_events_storage.get_events_by_filter(
            user_id="user_b",
            project_id=None
        )
        
        assert len(results) == 2
    
    async def test_get_events_by_filter_respects_time_range(
        self, mock_events_storage, sample_event_data
    ):
        """Test time range filtering in get_events_by_filter."""
        # Store an event
        await mock_events_storage.store_event_with_embedding(
            "user_time", "project_1", "event_recent", sample_event_data
        )
        
        # Manually set old timestamp
        key = ("user_time", "project_1", "event_recent")
        old_time = datetime.now(timezone.utc) - timedelta(days=30)
        mock_events_storage.events[key]['created_at'] = old_time
        
        # Query with 21 day range - should not find old event
        results = await mock_events_storage.get_events_by_filter(
            user_id="user_time",
            project_id="project_1",
            time_range_in_days=21
        )
        
        assert len(results) == 0
    
    async def test_get_events_by_filter_respects_limit(
        self, mock_events_storage, sample_event_data
    ):
        """Test result limit in get_events_by_filter."""
        # Store 10 events
        for i in range(10):
            await mock_events_storage.store_event_with_embedding(
                "user_limit", "project_1", f"event_{i}", sample_event_data
            )
        
        # Query with limit of 5
        results = await mock_events_storage.get_events_by_filter(
            user_id="user_limit",
            project_id="project_1",
            limit=5
        )
        
        assert len(results) == 5
    
    async def test_reset_with_user_and_project(
        self, mock_events_storage, sample_event_data
    ):
        """Test reset with user_id and project_id filters."""
        await mock_events_storage.store_event_with_embedding(
            "user_reset", "proj_a", "event_1", sample_event_data
        )
        await mock_events_storage.store_event_with_embedding(
            "user_reset", "proj_b", "event_2", sample_event_data
        )
        
        # Reset only proj_a
        count = await mock_events_storage.reset("user_reset", "proj_a")
        
        assert count == 1
        assert ("user_reset", "proj_a", "event_1") not in mock_events_storage.events
        assert ("user_reset", "proj_b", "event_2") in mock_events_storage.events
    
    async def test_reset_with_user_only(
        self, mock_events_storage, sample_event_data
    ):
        """Test reset with only user_id (all projects)."""
        await mock_events_storage.store_event_with_embedding(
            "user_reset_all", "proj_1", "event_1", sample_event_data
        )
        await mock_events_storage.store_event_with_embedding(
            "user_reset_all", "proj_2", "event_2", sample_event_data
        )
        
        count = await mock_events_storage.reset("user_reset_all", None)
        
        assert count == 2
        assert len(mock_events_storage.events) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventsHybridSearch:
    """Test hybrid search functionality for Events."""
    
    async def test_hybrid_search_with_project_id_filter(
        self, mock_events_storage, sample_event_data
    ):
        """Test hybrid search filters by project_id."""
        # Store events in different projects
        event_data_1 = {**sample_event_data, "event_tip": "travel to Japan"}
        event_data_2 = {**sample_event_data, "event_tip": "travel to Korea"}
        
        await mock_events_storage.store_event_with_embedding(
            "user_search", "proj_1", "event_1", event_data_1, [0.1] * 1536
        )
        await mock_events_storage.store_event_with_embedding(
            "user_search", "proj_2", "event_2", event_data_2, [0.2] * 1536
        )
        
        # Search only in proj_1
        results = await mock_events_storage.hybrid_search_events(
            user_id="user_search",
            query="travel Japan",
            query_vector=[0.15] * 1536,
            project_id="proj_1"
        )
        
        assert len(results) == 1
        assert results[0]['id'] == "event_1"
    
    async def test_hybrid_search_similarity_scoring(
        self, mock_events_storage, sample_event_data
    ):
        """Test that hybrid search returns similarity scores."""
        event_data = {**sample_event_data, "event_tip": "planning trip to Japan"}
        
        await mock_events_storage.store_event_with_embedding(
            "user_sim", "proj", "event_sim", event_data, [0.1] * 1536
        )
        
        results = await mock_events_storage.hybrid_search_events(
            user_id="user_sim",
            query="trip Japan",
            query_vector=[0.1] * 1536
        )
        
        assert len(results) > 0
        assert 'similarity' in results[0]
        assert 0.0 <= results[0]['similarity'] <= 1.0
    
    async def test_hybrid_search_respects_min_score(
        self, mock_events_storage, sample_event_data
    ):
        """Test hybrid search filters by minimum similarity score."""
        event_data = {**sample_event_data, "event_tip": "completely unrelated content"}
        
        await mock_events_storage.store_event_with_embedding(
            "user_score", "proj", "event_low_score", event_data, [0.1] * 1536
        )
        
        # Search with high min_score threshold
        results = await mock_events_storage.hybrid_search_events(
            user_id="user_score",
            query="travel Japan",
            query_vector=[0.9] * 1536,
            min_score=0.9
        )
        
        # Should not return low-scoring results
        assert len(results) == 0
    
    async def test_hybrid_search_respects_size_limit(
        self, mock_events_storage, sample_event_data
    ):
        """Test hybrid search respects size parameter."""
        # Store multiple matching events
        for i in range(10):
            event_data = {**sample_event_data, "event_tip": "travel to Japan"}
            await mock_events_storage.store_event_with_embedding(
                "user_size", "proj", f"event_{i}", event_data, [0.1] * 1536
            )
        
        results = await mock_events_storage.hybrid_search_events(
            user_id="user_size",
            query="travel Japan",
            query_vector=[0.1] * 1536,
            size=5
        )
        
        assert len(results) == 5
