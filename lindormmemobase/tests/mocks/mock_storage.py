"""
Mock storage backends for testing.

Provides in-memory implementations of storage interfaces that mimic
real database behavior without requiring actual database connections.
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
import uuid

from lindormmemobase.models.promise import Promise


class MockTableStorage:
    """
    Mock implementation of LindormTableStorage.
    
    Provides in-memory storage for user profiles with full CRUD operations.
    """
    
    def __init__(self):
        """Initialize mock table storage."""
        self.profiles: Dict[str, Dict[str, Any]] = {}  # profile_id -> profile data
        self.initialized = False
        self.call_counts = defaultdict(int)
    
    def initialize_tables(self):
        """Mock table initialization."""
        self.initialized = True
        self.call_counts["initialize_tables"] += 1
    
    async def add_profiles(
        self,
        user_id: str,
        profiles: List[str],
        attributes_list: List[Dict[str, str]],
        project_id: str = "default"
    ) -> Promise:
        """
        Add user profiles to storage.
        
        Args:
            user_id: User identifier
            profiles: List of profile content strings
            attributes_list: List of attribute dictionaries (topic, sub_topic)
            project_id: Project identifier
            
        Returns:
            Promise with list of created profile IDs
        """
        self.call_counts["add_profiles"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        if len(profiles) != len(attributes_list):
            return Promise.fail("Profiles and attributes lists must have same length")
        
        profile_ids = []
        now = datetime.now()
        
        for content, attributes in zip(profiles, attributes_list):
            profile_id = str(uuid.uuid4())
            self.profiles[profile_id] = {
                "user_id": user_id,
                "project_id": project_id,
                "profile_id": profile_id,
                "content": content,
                "attributes": attributes,
                "created_at": now,
                "updated_at": now,
                "update_hits": 0
            }
            profile_ids.append(profile_id)
        
        return Promise.ok(profile_ids)
    
    async def get_user_profiles(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None
    ) -> Promise:
        """
        Get user profiles with optional filtering.
        
        Returns Promise with list of profile dictionaries.
        """
        self.call_counts["get_user_profiles"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        results = []
        
        for profile_data in self.profiles.values():
            # Filter by user_id
            if profile_data["user_id"] != user_id:
                continue
            
            # Filter by project_id
            if project_id is not None and profile_data["project_id"] != project_id:
                continue
            
            # Filter by topics
            if topics and profile_data["attributes"].get("topic") not in topics:
                continue
            
            # Filter by subtopics
            if subtopics and profile_data["attributes"].get("sub_topic") not in subtopics:
                continue
            
            # Filter by time range
            if time_from and profile_data["created_at"] < time_from:
                continue
            if time_to and profile_data["created_at"] > time_to:
                continue
            
            results.append(profile_data.copy())
        
        return Promise.ok(results)
    
    async def update_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        profiles: List[str],
        attributes_list: List[Dict[str, str]],
        project_id: str = "default"
    ) -> Promise:
        """Update existing profiles."""
        self.call_counts["update_profiles"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        updated_ids = []
        now = datetime.now()
        
        for profile_id, content, attributes in zip(profile_ids, profiles, attributes_list):
            if profile_id in self.profiles:
                profile = self.profiles[profile_id]
                if profile["user_id"] == user_id and profile["project_id"] == project_id:
                    profile["content"] = content
                    profile["attributes"] = attributes
                    profile["updated_at"] = now
                    profile["update_hits"] += 1
                    updated_ids.append(profile_id)
        
        return Promise.ok(updated_ids)
    
    async def delete_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        project_id: str = "default"
    ) -> Promise:
        """Delete profiles."""
        self.call_counts["delete_profiles"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        deleted_count = 0
        
        for profile_id in profile_ids:
            if profile_id in self.profiles:
                profile = self.profiles[profile_id]
                if profile["user_id"] == user_id and profile["project_id"] == project_id:
                    del self.profiles[profile_id]
                    deleted_count += 1
        
        return Promise.ok(deleted_count)
    
    def reset(self):
        """Reset storage state."""
        self.profiles.clear()
        self.call_counts.clear()
        self.initialized = False


class MockSearchStorage:
    """
    Mock implementation of LindormSearchStorage.
    
    Provides in-memory vector search for events using simple similarity calculation.
    """
    
    def __init__(self):
        """Initialize mock search storage."""
        self.events: Dict[str, Dict[str, Any]] = {}  # event_id -> event data
        self.initialized = False
        self.call_counts = defaultdict(int)
    
    def initialize_indices(self):
        """Mock index initialization."""
        self.initialized = True
        self.call_counts["initialize_indices"] += 1
    
    async def add_event_gist(
        self,
        user_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Promise:
        """Add an event gist to search storage."""
        self.call_counts["add_event_gist"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        event_id = str(uuid.uuid4())
        now = datetime.now()
        
        self.events[event_id] = {
            "event_id": event_id,
            "user_id": user_id,
            "content": content,
            "embedding": embedding,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now
        }
        
        return Promise.ok(event_id)
    
    async def search_events(
        self,
        user_id: str,
        query_embedding: List[float],
        topk: int = 10,
        time_range_in_days: Optional[int] = None,
        similarity_threshold: float = 0.0
    ) -> Promise:
        """
        Search for similar events using vector similarity.
        
        Uses simple cosine similarity for mock implementation.
        """
        self.call_counts["search_events"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        results = []
        now = datetime.now()
        
        for event_data in self.events.values():
            if event_data["user_id"] != user_id:
                continue
            
            # Time filter
            if time_range_in_days:
                age_days = (now - event_data["created_at"]).days
                if age_days > time_range_in_days:
                    continue
            
            # Calculate simple similarity (mock cosine similarity)
            similarity = self._calculate_similarity(
                query_embedding,
                event_data["embedding"]
            )
            
            if similarity >= similarity_threshold:
                result = event_data.copy()
                result["similarity"] = similarity
                results.append(result)
        
        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top k
        return Promise.ok(results[:topk])
    
    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate mock cosine similarity."""
        # Simple dot product normalized (simplified for mock)
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def reset(self):
        """Reset storage state."""
        self.events.clear()
        self.call_counts.clear()
        self.initialized = False


class MockBufferStorage:
    """
    Mock implementation of LindormBufferStorage.
    
    Provides in-memory buffer for blob management.
    """
    
    def __init__(self):
        """Initialize mock buffer storage."""
        self.buffer: Dict[str, Dict[str, Any]] = {}  # blob_id -> blob data
        self.initialized = False
        self.call_counts = defaultdict(int)
    
    def initialize_tables(self):
        """Mock table initialization."""
        self.initialized = True
        self.call_counts["initialize_tables"] += 1
    
    async def insert_blob(
        self,
        user_id: str,
        blob_id: str,
        blob_data: Any,
        blob_type: str = "chat",
        status: str = "idle"
    ) -> Promise:
        """Insert a blob into buffer."""
        self.call_counts["insert_blob"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        now = datetime.now()
        
        self.buffer[blob_id] = {
            "user_id": user_id,
            "blob_id": blob_id,
            "blob_data": blob_data,
            "blob_type": blob_type,
            "status": status,
            "created_at": now,
            "updated_at": now
        }
        
        return Promise.ok(blob_id)
    
    async def get_blobs(
        self,
        user_id: str,
        blob_type: str = "chat",
        status: str = "idle"
    ) -> Promise:
        """Get blobs from buffer."""
        self.call_counts["get_blobs"] += 1
        
        if not self.initialized:
            return Promise.fail("Storage not initialized")
        
        results = []
        for blob_data in self.buffer.values():
            if (blob_data["user_id"] == user_id and
                blob_data["blob_type"] == blob_type and
                blob_data["status"] == status):
                results.append(blob_data.copy())
        
        return Promise.ok(results)
    
    async def update_blob_status(
        self,
        blob_id: str,
        status: str
    ) -> Promise:
        """Update blob status."""
        self.call_counts["update_blob_status"] += 1
        
        if blob_id in self.buffer:
            self.buffer[blob_id]["status"] = status
            self.buffer[blob_id]["updated_at"] = datetime.now()
            return Promise.ok(True)
        
        return Promise.fail(f"Blob {blob_id} not found")
    
    async def delete_blobs(
        self,
        blob_ids: List[str]
    ) -> Promise:
        """Delete blobs from buffer."""
        self.call_counts["delete_blobs"] += 1
        
        deleted_count = 0
        for blob_id in blob_ids:
            if blob_id in self.buffer:
                del self.buffer[blob_id]
                deleted_count += 1
        
        return Promise.ok(deleted_count)
    
    def reset(self):
        """Reset storage state."""
        self.buffer.clear()
        self.call_counts.clear()
        self.initialized = False
