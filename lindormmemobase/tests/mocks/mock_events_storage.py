"""Mock implementation of LindormEventsStorage for unit testing.

This mock provides in-memory storage for events testing without requiring
real database connections. It simulates the behavior of the real storage
layer for testing purposes.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from lindormmemobase.config import Config


class MockEventsStorage:
    """Mock storage for UserEvents table operations.
    
    Simulates LindormEventsStorage with in-memory dictionary storage.
    Key format: (user_id, project_id, event_id)
    """
    
    def __init__(self, config: Config):
        """Initialize mock storage with empty data store."""
        self.config = config
        self.events: Dict[tuple, Dict[str, Any]] = {}
        self.initialized = False
    
    def initialize_tables_and_indices(self):
        """Simulate table and index initialization."""
        self.initialized = True
    
    async def store_event_with_embedding(
            self,
            user_id: str,
            project_id: str,
            event_id: str,
            event_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        """Store event in mock storage."""
        key = (str(user_id), str(project_id), str(event_id))
        now = datetime.now(timezone.utc)
        
        self.events[key] = {
            'user_id': str(user_id),
            'project_id': str(project_id),
            'event_id': str(event_id),
            'event_data': event_data,
            'embedding': embedding,
            'created_at': now,
            'updated_at': now
        }
        
        return event_id
    
    async def delete_event(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> str:
        """Delete an event from mock storage."""
        key = (str(user_id), str(project_id), str(event_id))
        if key in self.events:
            del self.events[key]
        return event_id
    
    async def get_events_by_filter(
            self,
            user_id: str,
            project_id: Optional[str] = None,
            time_range_in_days: int = 21,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve events by filter criteria."""
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
        
        results = []
        for key, event in self.events.items():
            # Filter by user_id
            if event['user_id'] != str(user_id):
                continue
            
            # Filter by project_id if specified
            if project_id and event['project_id'] != str(project_id):
                continue
            
            # Filter by time range
            if event['created_at'] < time_cutoff:
                continue
            
            results.append({
                'id': event['event_id'],
                'event_data': event['event_data'],
                'created_at': event['created_at'],
                'updated_at': event['updated_at']
            })
        
        # Sort by created_at descending and apply limit
        results.sort(key=lambda x: x['created_at'], reverse=True)
        return results[:limit]
    
    async def hybrid_search_events(
            self,
            user_id: str,
            query: str,
            query_vector: List[float],
            size: int = 10,
            min_score: float = 0.6,
            time_range_in_days: int = 21,
            project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Simulate hybrid search with mock similarity scores."""
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
        
        results = []
        for key, event in self.events.items():
            # Filter by user_id
            if event['user_id'] != str(user_id):
                continue
            
            # Filter by project_id if specified
            if project_id and event['project_id'] != str(project_id):
                continue
            
            # Filter by time range
            if event['created_at'] < time_cutoff:
                continue
            
            # Mock similarity score based on query match in event_tip
            event_tip = event['event_data'].get('event_tip', '')
            # Simple mock: higher score if query words appear in event_tip
            query_words = query.lower().split()
            match_count = sum(1 for word in query_words if word in event_tip.lower())
            mock_similarity = min(0.9, 0.5 + (match_count * 0.1))
            
            if mock_similarity >= min_score:
                results.append({
                    'id': event['event_id'],
                    'event_data': event['event_data'],
                    'similarity': mock_similarity,
                    'created_at': event['created_at']
                })
        
        # Sort by similarity descending and apply size limit
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:size]
    
    async def reset(self, user_id: str, project_id: Optional[str] = None) -> int:
        """Reset events for specified user/project."""
        if user_id is None:
            # Full reset
            count = len(self.events)
            self.events.clear()
            return count
        
        # Filtered reset
        keys_to_delete = []
        for key, event in self.events.items():
            if event['user_id'] == str(user_id):
                if project_id is None or event['project_id'] == str(project_id):
                    keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.events[key]
        
        return len(keys_to_delete)
