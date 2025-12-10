"""Mock implementation of LindormEventGistsStorage for unit testing.

This mock provides in-memory storage for event gists testing without requiring
real database connections. It simulates the behavior of the real storage
layer for testing purposes.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from lindormmemobase.config import Config


class MockEventGistsStorage:
    """Mock storage for UserEventsGists table operations.
    
    Simulates LindormEventGistsStorage with in-memory dictionary storage.
    Key format: (user_id, project_id, event_id, gist_idx)
    """
    
    def __init__(self, config: Config):
        """Initialize mock storage with empty data store."""
        self.config = config
        self.gists: Dict[tuple, Dict[str, Any]] = {}
        self.initialized = False
    
    def initialize_tables_and_indices(self):
        """Simulate table and index initialization."""
        self.initialized = True
    
    async def store_event_gist_with_embedding(
            self,
            user_id: str,
            project_id: str,
            event_id: str,
            gist_idx: int,
            gist_text: str,
            embedding: Optional[List[float]] = None
    ) -> str:
        """Store event gist in mock storage."""
        key = (str(user_id), str(project_id), str(event_id), int(gist_idx))
        now = datetime.now(timezone.utc)
        
        self.gists[key] = {
            'user_id': str(user_id),
            'project_id': str(project_id),
            'event_id': str(event_id),
            'gist_idx': int(gist_idx),
            'event_gist_data': str(gist_text),
            'embedding': embedding,
            'created_at': now,
            'updated_at': now
        }
        
        return event_id
    
    async def delete_event_gist(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> str:
        """Delete event gists from mock storage."""
        keys_to_delete = [
            key for key in self.gists.keys()
            if key[0] == str(user_id) and key[1] == str(project_id) and key[2] == str(event_id)
        ]
        
        for key in keys_to_delete:
            del self.gists[key]
        
        return event_id
    
    async def delete_event_gists_by_event_id(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> int:
        """Delete all gists for a specific event."""
        keys_to_delete = [
            key for key in self.gists.keys()
            if key[0] == str(user_id) and key[1] == str(project_id) and key[2] == str(event_id)
        ]
        
        count = len(keys_to_delete)
        for key in keys_to_delete:
            del self.gists[key]
        
        return count
    
    async def get_event_gists_by_filter(
            self,
            user_id: str,
            project_id: Optional[str] = None,
            time_range_in_days: int = 21,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve event gists by filter criteria."""
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
        
        results = []
        for key, gist in self.gists.items():
            # Filter by user_id
            if gist['user_id'] != str(user_id):
                continue
            
            # Filter by project_id if specified
            if project_id and gist['project_id'] != str(project_id):
                continue
            
            # Filter by time range
            if gist['created_at'] < time_cutoff:
                continue
            
            # Create composite ID
            composite_id = f"{gist['event_id']}_{gist['gist_idx']}"
            
            results.append({
                'id': composite_id,
                'gist_data': {'content': gist['event_gist_data']},
                'created_at': gist['created_at'],
                'updated_at': gist['updated_at']
            })
        
        # Sort by created_at descending and apply limit
        results.sort(key=lambda x: x['created_at'], reverse=True)
        return results[:limit]
    
    async def hybrid_search_event_gists(
            self,
            user_id: str,
            query: str,
            query_vector: List[float],
            size: int = 10,
            min_score: float = 0.6,
            time_range_in_days: int = 21,
            project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Simulate hybrid search for event gists with mock similarity scores."""
        time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
        
        results = []
        for key, gist in self.gists.items():
            # Filter by user_id
            if gist['user_id'] != str(user_id):
                continue
            
            # Filter by project_id if specified
            if project_id and gist['project_id'] != str(project_id):
                continue
            
            # Filter by time range
            if gist['created_at'] < time_cutoff:
                continue
            
            # Mock similarity score based on query match in gist text
            gist_text = gist['event_gist_data']
            query_words = query.lower().split()
            match_count = sum(1 for word in query_words if word in gist_text.lower())
            mock_similarity = min(0.95, 0.5 + (match_count * 0.15))
            
            if mock_similarity >= min_score:
                # Create composite ID
                composite_id = f"{gist['event_id']}_{gist['gist_idx']}"
                
                results.append({
                    'id': composite_id,
                    'gist_data': {'content': gist['event_gist_data']},
                    'created_at': gist['created_at'],
                    'updated_at': gist['updated_at'],
                    'similarity': mock_similarity
                })
        
        # Sort by similarity descending and apply size limit
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:size]
    
    async def reset(self, user_id: str, project_id: Optional[str] = None) -> int:
        """Reset event gists for specified user/project."""
        if user_id is None:
            # Full reset
            count = len(self.gists)
            self.gists.clear()
            return count
        
        # Filtered reset
        keys_to_delete = []
        for key, gist in self.gists.items():
            if gist['user_id'] == str(user_id):
                if project_id is None or gist['project_id'] == str(project_id):
                    keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.gists[key]
        
        return len(keys_to_delete)
