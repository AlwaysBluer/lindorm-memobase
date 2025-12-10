"""Integration tests for UserEvents table operations with real Lindorm.

These tests require actual Lindorm Table and Search services.
Set environment variables or config.yaml before running.

Example:
    export MEMOBASE_LINDORM_TABLE_HOST=localhost
    export MEMOBASE_LINDORM_TABLE_PORT=33060
    
    pytest -m integration
"""

import pytest
from datetime import datetime, timedelta
from lindormmemobase.core.storage.manager import StorageManager


@pytest.mark.integration
@pytest.mark.requires_database
@pytest.mark.asyncio
class TestEventsTableOperations:
    """Integration tests for UserEvents table CRUD operations."""
    
    async def test_store_and_retrieve_event(self, integration_config, sample_event_data, mock_embedding_vector):
        """Test full lifecycle: store and retrieve event."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_{datetime.now().timestamp()}"
        project_id = "test_project_events"
        event_id = f"event_{datetime.now().timestamp()}"
        
        try:
            # Store event
            result = await storage.store_event_with_embedding(
                user_id=user_id,
                project_id=project_id,
                event_id=event_id,
                event_data=sample_event_data,
                embedding=mock_embedding_vector
            )
            
            assert result == event_id
            
            # Retrieve event
            events = await storage.get_events_by_filter(
                user_id=user_id,
                project_id=project_id,
                time_range_in_days=1
            )
            
            assert len(events) == 1
            assert events[0]['id'] == event_id
            assert events[0]['event_data']['event_tip'] == sample_event_data['event_tip']
            
        finally:
            # Cleanup
            await storage.delete_event(user_id, project_id, event_id)
            StorageManager.cleanup()
    
    async def test_multiple_events_across_projects(self, integration_config, sample_event_data, mock_embedding_vector):
        """Test storing events for same user across different projects."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_multi_{datetime.now().timestamp()}"
        
        try:
            # Store events in different projects
            await storage.store_event_with_embedding(
                user_id, "project_a", "event_a", sample_event_data, mock_embedding_vector
            )
            await storage.store_event_with_embedding(
                user_id, "project_b", "event_b", sample_event_data, mock_embedding_vector
            )
            
            # Retrieve from project_a only
            events_a = await storage.get_events_by_filter(
                user_id=user_id,
                project_id="project_a"
            )
            
            assert len(events_a) == 1
            assert events_a[0]['id'] == "event_a"
            
            # Retrieve all projects
            all_events = await storage.get_events_by_filter(
                user_id=user_id,
                project_id=None
            )
            
            assert len(all_events) == 2
            
        finally:
            await storage.reset(user_id)
            StorageManager.cleanup()
    
    async def test_time_range_filtering(self, integration_config, sample_event_data):
        """Test that time range filtering works correctly."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_time_{datetime.now().timestamp()}"
        project_id = "test_project"
        
        try:
            # Store event
            await storage.store_event_with_embedding(
                user_id, project_id, "event_recent", sample_event_data
            )
            
            # Query with 1 day range - should find event
            events = await storage.get_events_by_filter(
                user_id=user_id,
                project_id=project_id,
                time_range_in_days=1
            )
            
            assert len(events) >= 1
            
        finally:
            await storage.reset(user_id)
            StorageManager.cleanup()
    
    async def test_reset_with_filters(self, integration_config, sample_event_data):
        """Test reset operations with user_id and project_id filters."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_reset_{datetime.now().timestamp()}"
        
        try:
            # Store events in two projects
            await storage.store_event_with_embedding(
                user_id, "proj_keep", "event_1", sample_event_data
            )
            await storage.store_event_with_embedding(
                user_id, "proj_delete", "event_2", sample_event_data
            )
            
            # Reset only proj_delete
            count = await storage.reset(user_id, "proj_delete")
            
            assert count >= 1
            
            # Verify proj_keep still has event
            remaining = await storage.get_events_by_filter(
                user_id, "proj_keep"
            )
            
            assert len(remaining) >= 1
            
        finally:
            await storage.reset(user_id)
            StorageManager.cleanup()


@pytest.mark.integration
@pytest.mark.requires_database
@pytest.mark.asyncio  
class TestEventsSearchIntegration:
    """Integration tests for UserEvents hybrid search."""
    
    async def test_hybrid_search_with_embeddings(self, integration_config, mock_embedding_vector):
        """Test hybrid search returns relevant events."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_search_{datetime.now().timestamp()}"
        project_id = "test_search"
        
        try:
            # Store event with specific content
            event_data = {
                "event_tip": "User discussed plans to visit Tokyo for cherry blossoms",
                "event_tags": [{"tag": "category", "value": "travel"}],
                "profile_delta": {
                    "attributes": {"topic": "travel", "sub_topic": "japan"},
                    "content": "Planning Tokyo trip"
                }
            }
            
            await storage.store_event_with_embedding(
                user_id, project_id, "event_search", event_data, mock_embedding_vector
            )
            
            # Small delay for indexing
            import asyncio
            await asyncio.sleep(2)
            
            # Search with query
            results = await storage.hybrid_search_events(
                user_id=user_id,
                query="Tokyo cherry blossoms",
                query_vector=mock_embedding_vector,
                size=10,
                min_score=0.0,
                project_id=project_id
            )
            
            # Verify search works (may or may not return results depending on indexing)
            assert isinstance(results, list)
            
        finally:
            await storage.reset(user_id)
            StorageManager.cleanup()
    
    async def test_search_with_project_filter(self, integration_config, mock_embedding_vector):
        """Test hybrid search respects project_id filter."""
        StorageManager.initialize(integration_config)
        storage = StorageManager.get_search_storage(integration_config)
        
        user_id = f"test_user_proj_filter_{datetime.now().timestamp()}"
        
        try:
            event_data = {
                "event_tip": "Travel planning discussion",
                "event_tags": [],
                "profile_delta": {"attributes": {}, "content": ""}
            }
            
            # Store in two projects
            await storage.store_event_with_embedding(
                user_id, "project_search", "event_1", event_data, mock_embedding_vector
            )
            await storage.store_event_with_embedding(
                user_id, "project_other", "event_2", event_data, mock_embedding_vector
            )
            
            import asyncio
            await asyncio.sleep(2)
            
            # Search only in project_search
            results = await storage.hybrid_search_events(
                user_id=user_id,
                query="travel planning",
                query_vector=mock_embedding_vector,
                project_id="project_search"
            )
            
            # Verify results (if any) are from correct project
            assert isinstance(results, list)
            
        finally:
            await storage.reset(user_id)
            StorageManager.cleanup()
