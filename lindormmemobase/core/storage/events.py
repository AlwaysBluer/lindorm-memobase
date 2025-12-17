import json
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from opensearchpy import OpenSearch
from typing import Optional, Dict, List, Any

from lindormmemobase.utils.tools import validate_and_format_embedding
from lindormmemobase.utils.errors import SearchStorageError, StorageError
from lindormmemobase.config import Config, LOG
from .base import LindormStorageBase
from .manager import StorageManager


# Default project_id constant
DEFAULT_PROJECT_ID = "default"

# Backward compatibility - delegate to StorageManager
def get_lindorm_search_storage(config: Config) -> 'LindormEventsStorage':
    """Get or create a global LindormEventsStorage instance - delegates to StorageManager."""
    return StorageManager.get_search_storage(config)


# class OpenSearchEventStorage:
# Lindorm is compatible with Opensearch .
class LindormEventsStorage(LindormStorageBase):
    def __init__(self, config: Config):
        super().__init__(config)
        self.event_index_name = f"{self.config.lindorm_table_database}.UserEvents.srh_idx"
        # OpenSearch client for search operations
        self.client = OpenSearch(
            hosts=[{
                'host': config.lindorm_search_host,
                'port': config.lindorm_search_port
            }],
            http_auth=(
                config.lindorm_search_username,
                config.lindorm_search_password) if config.lindorm_search_username else None,
            use_ssl=config.lindorm_search_use_ssl,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
        # Don't call _ensure methods in __init__ anymore
        # Tables and indices are created explicitly via initialize_tables_and_indices()
    
    def _get_pool_name(self) -> str:
        """Return unique pool name for events storage."""
        return "memobase_events_pool"
    
    def _get_pool_config(self) -> dict:
        """Return connection pool configuration for events storage."""
        return {
            'host': self.config.lindorm_table_host,
            'port': self.config.lindorm_table_port,
            'user': self.config.lindorm_table_username,
            'password': self.config.lindorm_table_password,
            'database': self.config.lindorm_table_database,
            'pool_size': self.config.lindorm_table_pool_size
        }
    
    def initialize_tables_and_indices(self):
        """Create UserEvents table and search index. Called during StorageManager initialization."""
        # Configure Lindorm system settings first (from base class)
        # self._configure_lindorm_settings()
        
        self._create_table()
        self._create_search_index()
    
    def _create_table(self):
        """Create UserEvents wide table via SQL."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create UserEvents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UserEvents (
                    user_id VARCHAR(255) NOT NULL,
                    project_id VARCHAR(255) NOT NULL,
                    event_id VARCHAR(255) NOT NULL,
                    event_data JSON,
                    embedding VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, project_id, event_id)
                )
            """)
            conn.commit()
            LOG.info("UserEvents table created/verified")
        finally:
            cursor.close()
            conn.close()
    
    def _create_search_index(self):
        """Create search index for UserEvents table via SQL CREATE INDEX.
        
        Lindorm automatically syncs table changes to search indices.
        No need to write directly to search indices via OpenSearch API.
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create search index on UserEvents table with fine-grained event_data mapping
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS srh_idx USING SEARCH ON UserEvents(
                    user_id,
                    project_id,
                    event_id,
                    created_at,
                    updated_at,
                    event_data(mapping='{{
                        "properties": {{
                            "event_tip": {{
                                "type": "text"
                            }},
                            "event_tags": {{
                                "type": "nested",
                                "properties": {{
                                    "tag":   {{ "type": "keyword" }}, 
                                    "value": {{ "type": "keyword" }}  
                                }}
                            }},
                            "profile_delta": {{
                                "type": "nested",
                                "properties": {{
                                    "attributes": {{
                                        "properties": {{
                                            "sub_topic": {{
                                                "type": "keyword"
                                            }},
                                            "topic": {{
                                                "type": "keyword"
                                            }}
                                        }}
                                    }},
                                    "content": {{
                                        "type": "text"
                                    }}
                                }}
                            }}
                        }}
                    }}'),
                    embedding(mapping='{{
                        "type": "knn_vector",
                        "dimension": {self.config.embedding_dim},
                        "data_type": "float",
                        "method": {{
                            "engine": "lvector",
                            "name": "hnsw",
                            "space_type": "l2",
                            "parameters": {{
                                "m": 24,
                                "ef_construction": 500
                            }}
                        }}
                    }}')
                ) PARTITION BY hash(user_id) WITH (
                    SOURCE_SETTINGS='{{
                        "excludes": ["embedding"]
                    }}',
                    INDEX_SETTINGS='{{
                        "index": {{
                            "knn": true,
                            "knn_routing": true,
                            "knn.vector_empty_value_to_keep": true
                        }}
                    }}'
                )
            """)
            
            conn.commit()
            LOG.info("UserEvents search index created/verified")
        finally:
            cursor.close()
            conn.close()

    async def store_event_with_embedding(
            self,
            user_id: str,
            project_id: str,
            event_id: str,
            event_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        """Store event in UserEvents table via SQL INSERT."""
        def _store_event_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            # Use default project_id if not provided
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc)
                
                # Convert event_data dict to JSON string
                event_data_json = json.dumps(event_data)
                
                # Validate and format embedding with strict dimension check
                embedding_str = validate_and_format_embedding(
                    embedding, 
                    self.config.embedding_dim, 
                    str(user_id)
                )
                
                cursor.execute(
                    """
                    INSERT INTO UserEvents 
                    (user_id, project_id, event_id, event_data, embedding, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(user_id), str(actual_project_id), str(event_id), 
                     event_data_json, embedding_str, now, now)
                )
                
                conn.commit()
                return event_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to store event: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _store_event_sync,
            "Failed to store event"
        )



    async def delete_event(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> str:
        """Delete an event from UserEvents table via SQL.
        
        Note: Administrative use only. Events are immutable in normal operation.
        Used for data cleanup or GDPR compliance.
        Lindorm automatically syncs deletion to search indices.
        """
        def _delete_event_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor()
                
                # DELETE requires all primary key columns in Lindorm
                cursor.execute(
                    """
                    DELETE FROM UserEvents 
                    WHERE user_id = %s AND project_id = %s AND event_id = %s
                    """,
                    (str(user_id), str(actual_project_id), str(event_id))
                )
                
                conn.commit()
                return event_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to delete event: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _delete_event_sync,
            "Failed to delete event"
        )

    async def get_events_by_filter(
            self,
            user_id: str,
            project_id: Optional[str] = None,
            time_range_in_days: int = 21,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve UserEvents by SQL filters without vector search.
        
        Args:
            user_id: User identifier to filter by
            project_id: Optional project filter. If None, searches all projects.
            time_range_in_days: Number of days to look back from now
            limit: Maximum number of results to return
        
        Returns:
            List of event dictionaries with id, event_data, created_at, updated_at
        """
        def _get_events_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor(dictionary=True)
                
                # Calculate time cutoff
                time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
                
                # Build query based on whether project_id is specified
                if project_id:
                    query = """
                        SELECT event_id, event_data, created_at, updated_at
                        FROM UserEvents
                        WHERE user_id = %s AND project_id = %s AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (str(user_id), str(actual_project_id), time_cutoff, limit))
                else:
                    query = """
                        SELECT event_id, event_data, created_at, updated_at
                        FROM UserEvents
                        WHERE user_id = %s AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (str(user_id), time_cutoff, limit))
                
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    # Parse event_data from JSON string to dict
                    event_data_dict = json.loads(row['event_data']) if isinstance(row['event_data'], str) else row['event_data']
                    
                    results.append({
                        'id': row['event_id'],
                        'event_data': event_data_dict,
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })
                
                return results
            except Exception as e:
                raise StorageError(f"Failed to get events by filter: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _get_events_sync,
            "Failed to get events by filter"
        )

    async def reset(self, user_id:str, project_id: Optional[str] = None) -> int:
        """Reset (delete all) events data from UserEvents table.
        
        Args:
            user_id: If provided, only delete data for this user. If None, delete all data.
            project_id: If provided, only delete data for this project. If None, delete all projects.
        
        Returns:
            Number of deleted event rows
        
        Note: Administrative use only. Use with caution.
        """
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                
                events_count = 0
                
                if user_id and project_id:
                    # Delete for specific user and project
                    cursor.execute(
                        "DELETE FROM UserEvents WHERE user_id = %s AND project_id = %s",
                        (user_id, project_id)
                    )
                    events_count = cursor.rowcount
                elif user_id:
                    # Delete all projects for this user
                    cursor.execute(
                        "DELETE FROM UserEvents WHERE user_id = %s",
                        (user_id,)
                    )
                    events_count = cursor.rowcount
                elif project_id:
                    raise ValueError("Project ID cannot be specified without user ID") 
                else:
                    cursor.execute("TRUNCATE TABLE UserEvents")
                    events_count = -1
                
                conn.commit()
                return events_count
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()
        
        try:
            events_count = await self._execute_sync_operation(
                _reset_sync,
                "Failed to reset events"
            )
            LOG.info(
                f"Events reset: deleted {events_count} events "
                f"(user_id={user_id}, project_id={project_id})"
            )
            return events_count
        except Exception as e:
            raise StorageError(f"Failed to reset events: {str(e)}") from e

    async def hybrid_search_events(
            self,
            user_id: str,
            query: str,
            query_vector: List[float],
            size: int = 10,
            min_score: float = 0.6,
            time_range_in_days: int = 21,
            project_id: Optional[str] = None,
            topics: Optional[List[str]] = None,
            subtopics: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
            tag_values: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid vector + keyword search on UserEvents table with advanced filtering.
        
        Args:
            user_id: User identifier
            query: Text query for keyword matching
            query_vector: Query embedding vector
            size: Maximum number of results
            min_score: Minimum similarity score
            time_range_in_days: Number of days to look back
            project_id: Optional project filter. If None, searches across all projects.
            topics: Filter by event_data.profile_delta.attributes.topic (OR logic)
            subtopics: Filter by event_data.profile_delta.attributes.sub_topic (OR logic)
            tags: Filter by event_data.event_tags.tag (OR logic)
            tag_values: Filter by event_data.event_tags.value (OR logic)
        
        Returns:
            List of matching events with metadata
        """
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            # Convert to milliseconds timestamp for TIMESTAMP field
            time_cutoff_ms = int(time_cutoff.timestamp() * 1000)
            
            # Build base filter conditions
            filter_conditions = [
                {"term": {"user_id": user_id}},
                {"range": {"created_at": {"gte": time_cutoff_ms}}},
                {"match": {"event_data.event_tip": {"query": query}}}
            ]
            
            # Add project_id filter if specified
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})
            
            # Add topic filter (OR logic for multiple topics)
            if topics:
                filter_conditions.append({
                    "terms": {"event_data.profile_delta.attributes.topic": topics}
                })
            
            # Add subtopic filter (OR logic for multiple subtopics)
            if subtopics:
                filter_conditions.append({
                    "terms": {"event_data.profile_delta.attributes.sub_topic": subtopics}
                })
            
            # Add tag name filter (OR logic for multiple tags)
            if tags:
                filter_conditions.append({
                    "terms": {"event_data.event_tags.tag": tags}
                })
            
            # Add tag value filter (OR logic for multiple values)
            if tag_values:
                filter_conditions.append({
                    "terms": {"event_data.event_tags.value": tag_values}
                })
            
            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["embedding", "_searchindex_id"]
                },
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": [{"bool": {"must": filter_conditions}}]
                                }
                            },
                            "k": size,
                        }
                    }
                },
                "ext": {
                    "lvector": {
                        "min_score": str(min_score),
                        "hybrid_search_type": "filter_rrf",
                        "filter_type": "pre_filter",
                        "rrf_knn_weight_factor": "0.4",
                        "client_refactor":"true",
                        "rrf_rank_constant": "2"
                    }
                }
            }
            
            response = self.client.search(
                index=self.event_index_name,
                body=search_query,
                routing=user_id
            )

            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_id'],
                    'event_data': hit['_source']['event_data'],
                    'similarity': hit['_score'],
                    'created_at': hit['_source']['created_at']
                })

            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to search events: {str(e)}") from e



async def search_user_events_with_embedding(
        user_id: str,
        query: str,
        query_vector: List[float],
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        tag_values: Optional[List[str]] = None
)-> List[Dict[str, Any]]:
    """Search user events with embedding vector and advanced filters.
    
    Args:
        user_id: User identifier
        query: Text query for keyword matching
        query_vector: Query embedding vector
        config: Configuration object
        topk: Maximum number of results
        similarity_threshold: Minimum similarity score
        time_range_in_days: Number of days to look back
        project_id: Optional project filter
        topics: Filter by profile delta topics (OR logic)
        subtopics: Filter by profile delta subtopics (OR logic)
        tags: Filter by event tag names (OR logic)
        tag_values: Filter by event tag values (OR logic)
    
    Returns:
        List of matching events with metadata
    """
    storage = get_lindorm_search_storage(config)
    return await storage.hybrid_search_events(
        user_id, query, query_vector, topk,
        similarity_threshold, time_range_in_days, project_id,
        topics=topics,
        subtopics=subtopics,
        tags=tags,
        tag_values=tag_values
    )


async def store_event_with_embedding(
        user_id: str,
        project_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.store_event_with_embedding(user_id, project_id, event_id, event_data, embedding)



async def delete_event(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> str:
    """Delete event - administrative use only."""
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event(user_id, project_id, event_id)


async def get_events_by_filter(
        user_id: str,
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        config: Config = None
) -> List[Dict[str, Any]]:
    """Retrieve UserEvents by SQL filters without vector search."""
    storage = get_lindorm_search_storage(config)
    return await storage.get_events_by_filter(user_id, project_id, time_range_in_days, limit)
