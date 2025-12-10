"""Storage layer for UserEventsGists table operations.

This module handles storage operations specifically for event gists (UserEventsGists table),
separated from full event storage for better code organization and maintainability.

This is an independent service with its own table, index, and OpenSearch client.
"""
from datetime import datetime, timezone, timedelta
from opensearchpy import OpenSearch
from mysql.connector import pooling
from typing import Optional, Dict, List, Any

from lindormmemobase.utils.errors import StorageError, SearchStorageError
from lindormmemobase.config import Config, TRACE_LOG, LOG
from .base import LindormStorageBase
from .events import validate_and_format_embedding

# Default project_id constant
DEFAULT_PROJECT_ID = "default"

class LindormEventGistsStorage(LindormStorageBase):
    """Independent storage handler for UserEventsGists table operations.
    
    This class has its own connection pool, OpenSearch client, and manages
    the UserEventsGists table and search index independently.
    """
    
    def __init__(self, config: Config):
        """Initialize independent storage for event gists.
        
        Args:
            config: Configuration object
        """
        super().__init__(config)
        self.event_gist_index_name = f"{self.config.lindorm_table_database}.UserEventsGists.srh_idx"
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
    
    def _get_pool_name(self) -> str:
        """Return unique pool name for event gists storage."""
        return "memobase_event_gists_pool"
    
    def _get_pool_config(self) -> dict:
        """Return connection pool configuration for event gists storage."""
        return {
            'host': self.config.lindorm_table_host,
            'port': self.config.lindorm_table_port,
            'user': self.config.lindorm_table_username,
            'password': self.config.lindorm_table_password,
            'database': self.config.lindorm_table_database,
            'pool_size': self.config.lindorm_table_pool_size
        }
    
    def initialize_tables_and_indices(self):
        """Create UserEventsGists table and search index.
        
        Called during StorageManager initialization.
        """
        # Configure Lindorm system settings first (from base class)
        # self._configure_lindorm_settings()
        self._create_table()
        self._create_search_index()
    
    def _create_table(self):
        """Create UserEventsGists wide table via SQL."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create UserEventsGists table with gist_idx for one-to-many relationship
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UserEventsGists (
                    user_id VARCHAR(255) NOT NULL,
                    project_id VARCHAR(255) NOT NULL,
                    event_id VARCHAR(255) NOT NULL,
                    gist_idx INT NOT NULL,
                    event_gist_data VARCHAR NOT NULL,
                    embedding VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, project_id, event_id, gist_idx)
                )
            """)
            
            conn.commit()
            LOG.info("UserEventsGists table created/verified")
        finally:
            cursor.close()
            conn.close()
    
    def _create_search_index(self):
        """Create search index for UserEventsGists table via SQL CREATE INDEX.
        
        Lindorm automatically syncs table changes to search indices.
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create search index on UserEventsGists table
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS srh_idx USING SEARCH ON UserEventsGists(
                    user_id,
                    project_id,
                    event_id,
                    gist_idx,
                    created_at,
                    updated_at,
                    event_gist_data(type=text,analyzer=ik,indexed=true),
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
                            "knn": "true",
                            "knn_routing": "true",
                            "knn.vector_empty_value_to_keep": true
                        }}
                    }}'
                )
            """)
            
            conn.commit()
            LOG.info("UserEventsGists search index created/verified")
        finally:
            cursor.close()
            conn.close()
    
    async def store_event_gist_with_embedding(
            self,
            user_id: str,
            project_id: str,
            event_id: str,
            gist_idx: int,
            gist_text: str,
            embedding: Optional[List[float]] = None
    ) -> str:
        """Store event gist in UserEventsGists table via SQL INSERT.
        
        Args:
            user_id: User identifier
            project_id: Project identifier
            event_id: Event identifier this gist belongs to
            gist_idx: Index of this gist within the event (0-based)
            gist_text: Plain text gist content (VARCHAR, not JSON)
            embedding: Optional embedding vector for semantic search
        
        Returns:
            event_id of the stored gist
        
        Note: Multiple gists for the same event_id are stored with different gist_idx.
        """
        def _store_gist_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            # Use default project_id if not provided
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc)
                
                # Validate and format embedding with strict dimension check
                embedding_str = validate_and_format_embedding(
                    embedding, 
                    self.config.embedding_dim, 
                    str(user_id)
                )
                
                cursor.execute(
                    """
                    INSERT INTO UserEventsGists 
                    (user_id, project_id, event_id, gist_idx, event_gist_data, embedding, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(user_id), str(actual_project_id), str(event_id), 
                     int(gist_idx), str(gist_text), embedding_str, now, now)
                )
                
                conn.commit()
                return event_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to store event gist: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _store_gist_sync,
            "Failed to store event gist"
        )
    
    async def delete_event_gist(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> str:
        """Delete event gists from UserEventsGists table via SQL.
        
        Note: Administrative use only. Events are immutable in normal operation.
        Used for data cleanup or GDPR compliance.
        Lindorm automatically syncs deletion to search indices.
        """
        def _delete_gist_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor()
                # DELETE requires all primary key columns in Lindorm
                cursor.execute(
                    """
                    DELETE FROM UserEventsGists 
                    WHERE user_id = %s AND project_id = %s AND event_id = %s
                    """,
                    (str(user_id), str(actual_project_id), str(event_id))
                )
                
                conn.commit()
                return event_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to delete event gist: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _delete_gist_sync,
            "Failed to delete event gist"
        )
    
    async def delete_event_gists_by_event_id(
            self,
            user_id: str,
            project_id: str,
            event_id: str
    ) -> int:
        """Delete all gists associated with an event_id via SQL.
        
        Note: Administrative use only. Events are immutable in normal operation.
        Used for cascade cleanup when deleting an event.
        Lindorm automatically syncs deletion to search indices.
        """
        def _delete_gists_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor()
                
                # First count how many will be deleted
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM UserEventsGists 
                    WHERE user_id = %s AND project_id = %s AND event_id = %s
                    """,
                    (str(user_id), str(actual_project_id), str(event_id))
                )
                count = cursor.fetchone()[0]
                
                # Then delete them
                cursor.execute(
                    """
                    DELETE FROM UserEventsGists 
                    WHERE user_id = %s AND project_id = %s AND event_id = %s
                    """,
                    (str(user_id), str(actual_project_id), str(event_id))
                )
                
                conn.commit()
                return count
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to delete event gists: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _delete_gists_sync,
            "Failed to delete event gists"
        )
    
    async def get_event_gists_by_filter(
            self,
            user_id: str,
            project_id: Optional[str] = None,
            time_range_in_days: int = 21,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve UserEventsGists by SQL filters without vector search.
        
        Args:
            user_id: User identifier to filter by
            project_id: Optional project filter. If None, searches all projects.
            time_range_in_days: Number of days to look back from now
            limit: Maximum number of results to return
        
        Returns:
            List of gist dictionaries with id, gist_data, created_at, updated_at
        """
        def _get_gists_sync():
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
                        SELECT event_id, gist_idx, event_gist_data, created_at, updated_at
                        FROM UserEventsGists
                        WHERE user_id = %s AND project_id = %s AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (str(user_id), str(actual_project_id), time_cutoff, limit))
                else:
                    query = """
                        SELECT event_id, gist_idx, event_gist_data, created_at, updated_at
                        FROM UserEventsGists
                        WHERE user_id = %s AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cursor.execute(query, (str(user_id), time_cutoff, limit))
                
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    # Create composite ID from event_id and gist_idx
                    composite_id = f"{row['event_id']}_{row['gist_idx']}"
                    
                    results.append({
                        'id': composite_id,
                        'gist_data': {'content': row['event_gist_data']},
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })
                
                return results
            except Exception as e:
                raise StorageError(f"Failed to get event gists by filter: {str(e)}") from e
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _get_gists_sync,
            "Failed to get event gists by filter"
        )
    
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
        """Hybrid vector + keyword search on UserEventsGists table.
        
        Args:
            user_id: User identifier
            query: Text query for keyword matching
            query_vector: Embedding vector for similarity search
            size: Maximum number of results
            min_score: Minimum similarity score threshold
            time_range_in_days: Number of days to look back
            project_id: Optional project filter. If None, searches across all projects.
        
        Returns:
            List of gist dictionaries with id, gist_data, created_at, updated_at, similarity
        """
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            # Convert to milliseconds timestamp for TIMESTAMP field
            time_cutoff_ms = int(time_cutoff.timestamp() * 1000)
            
            # Build filter conditions
            filter_conditions = [
                {"term": {"user_id": user_id}},
                {"range": {"created_at": {"gte": time_cutoff_ms}}},
                {"match": {"event_gist_data": {"query": query}}}
            ]
            
            # Add project_id filter if specified
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})
            
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
                        "filter_type": "pre_filter",
                        "hybrid_search_type": "filter_rrf",
                        "rrf_knn_weight_factor": "0.5",
                        "client_refactor":"true"
                    }
                }
            }

            
            response = self.client.search(
                index=self.event_gist_index_name,
                body=search_query,
                routing=user_id
            )
            
            if not response or 'hits' not in response or 'hits' not in response['hits']:
                TRACE_LOG.error(user_id, f"Invalid search response structure: {response}")
                return []

            gists = []
            for hit in response['hits']['hits']:
                if '_source' not in hit:
                    TRACE_LOG.error(user_id, f"Missing _source in search hit: {hit.keys()}")
                    continue
                source = hit['_source']
                # Check if required fields exist in source
                if 'event_gist_data' not in source or 'created_at' not in source:
                    TRACE_LOG.error(user_id, f"Missing required fields in _source: {source.keys()}")
                    continue
                similarity = hit.get('_score', 0.0)
                # Wrap plain text gist in dict for backward compatibility
                gists.append({
                    "id": hit['_id'],
                    "gist_data": {"content": source['event_gist_data']},
                    "created_at": source['created_at'],
                    "updated_at": source.get('updated_at', source['created_at']),
                    "similarity": similarity
                })

            return gists
        except Exception as e:
            raise SearchStorageError(f"Failed to search gist events: {str(e)}") from e
    
    async def reset(self, user_id: str, project_id: Optional[str] = None) -> int:
        """Reset (delete all) event gists data from UserEventsGists table.
        
        Args:
            user_id: If provided, only delete data for this user. If None, delete all data.
            project_id: If provided, only delete data for this project. If None, delete all projects.
        
        Returns:
            Number of deleted event gist rows
        
        Note: Administrative use only. Use with caution.
        """
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                
                gists_count = 0
                
                if user_id and project_id:
                    # Delete for specific user and project
                    cursor.execute(
                        "DELETE FROM UserEventsGists WHERE user_id = %s AND project_id = %s",
                        (user_id, project_id)
                    )
                    gists_count = cursor.rowcount
                elif user_id:
                    # Delete all projects for this user
                    cursor.execute(
                        "DELETE FROM UserEventsGists WHERE user_id = %s",
                        (user_id,)
                    )
                    gists_count = cursor.rowcount
                elif project_id:
                    raise ValueError("Project ID cannot be specified without user ID")
                else:
                    cursor.execute("TRUNCATE TABLE UserEventsGists")
                    gists_count = -1
                
                conn.commit()
                return gists_count
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()
        
        try:
            gists_count = await self._execute_sync_operation(
                _reset_sync,
                "Failed to reset event gists"
            )
            TRACE_LOG.info(
                user_id or "system",
                f"Event gists reset: deleted {gists_count} gists "
                f"(user_id={user_id}, project_id={project_id})"
            )
            return gists_count
        except Exception as e:
            raise StorageError(f"Failed to reset event gists: {str(e)}") from e


# Backward compatibility - delegate to StorageManager
def get_lindorm_event_gists_storage(config: Config) -> 'LindormEventGistsStorage':
    """Get or create a LindormEventGistsStorage instance."""
    from .manager import StorageManager
    return StorageManager.get_event_gists_storage(config)


# Module-level wrapper functions for convenient access
async def store_event_gist_with_embedding(
        user_id: str,
        project_id: str,
        event_id: str,
        gist_idx: int,
        gist_text: str,
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    """Store event gist with embedding - module-level wrapper."""
    storage = get_lindorm_event_gists_storage(config)
    return await storage.store_event_gist_with_embedding(user_id, project_id, event_id, gist_idx, gist_text, embedding)


async def delete_event_gist(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> str:
    """Delete event gist - administrative use only."""
    storage = get_lindorm_event_gists_storage(config)
    return await storage.delete_event_gist(user_id, project_id, event_id)


async def delete_event_gists_by_event_id(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> int:
    """Delete all event gists for an event - administrative use only."""
    storage = get_lindorm_event_gists_storage(config)
    return await storage.delete_event_gists_by_event_id(user_id, project_id, event_id)


async def get_event_gists_by_filter(
        user_id: str,
        project_id: Optional[str] = None,
        time_range_in_days: int = 21,
        limit: int = 20,
        config: Config = None
) -> List[Dict[str, Any]]:
    """Retrieve UserEventsGists by SQL filters without vector search."""
    storage = get_lindorm_event_gists_storage(config)
    return await storage.get_event_gists_by_filter(user_id, project_id, time_range_in_days, limit)


async def search_user_event_gists_with_embedding(
        user_id: str,
        query: str,
        query_vector: List[float],
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search event gists with embedding vector - module-level wrapper."""
    storage = get_lindorm_event_gists_storage(config)
    return await storage.hybrid_search_event_gists(user_id, query, query_vector, topk, similarity_threshold, time_range_in_days, project_id)
