import json
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from opensearchpy import OpenSearch
from mysql.connector import pooling
from typing import Optional, Dict, List, Any

from lindormmemobase.utils.tools import event_embedding_str
from ...utils.errors import SearchStorageError, StorageError
from ...config import Config, TRACE_LOG


def validate_and_format_embedding(embedding: Optional[List[float]], expected_dim: int, user_id: str = "system") -> Optional[str]:
    """Validate embedding format and dimensions, return JSON string or None.
    
    Args:
        embedding: Embedding vector to validate
        expected_dim: Expected dimension from config
        user_id: User ID for logging purposes
    
    Returns:
        JSON string representation of embedding if valid, empty string otherwise
    """
    if embedding is None:
        return None
    
    try:
        # Convert to list if numpy array
        if hasattr(embedding, 'tolist'):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
        
        # Validate it's a list
        if not isinstance(embedding_list, list):
            TRACE_LOG.warning(user_id, f"Invalid embedding type: {type(embedding_list)}, expected list. Using empty string.")
            return ""
        
        # Validate dimension
        if len(embedding_list) != expected_dim:
            TRACE_LOG.warning(user_id, f"Invalid embedding dimension: {len(embedding_list)}, expected {expected_dim}. Using empty string.")
            return ""
        
        # Validate all elements are numbers
        for i, val in enumerate(embedding_list):
            if not isinstance(val, (int, float)):
                TRACE_LOG.warning(user_id, f"Invalid embedding value at index {i}: {type(val)}, expected number. Using empty string.")
                return ""
            # Check for NaN or Inf
            if isinstance(val, float) and (val != val or abs(val) == float('inf')):
                TRACE_LOG.warning(user_id, f"Invalid embedding value at index {i}: {val} (NaN or Inf). Using empty string.")
                return ""
        
        # Return JSON string representation
        return json.dumps(embedding_list)
    
    except Exception as e:
        TRACE_LOG.warning(user_id, f"Failed to validate embedding: {str(e)}. Using empty string.")
        return ""

# Default project_id constant
DEFAULT_PROJECT_ID = "default"

# Backward compatibility - delegate to StorageManager
def get_lindorm_search_storage(config: Config) -> 'LindormEventsStorage':
    """Get or create a global LindormEventsStorage instance - delegates to StorageManager."""
    from .manager import StorageManager
    return StorageManager.get_search_storage(config)


# class OpenSearchEventStorage:
# Lindorm is compatible with Opensearch .
class LindormEventsStorage:
    def __init__(self, config: Config):
        self.config = config
        self.pool = None  # SQL connection pool for table operations
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
    
    def _get_pool(self):
        """Get or create SQL connection pool for table operations."""
        if self.pool is None:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="memobase_events_pool",
                pool_size=self.config.lindorm_table_pool_size,
                pool_reset_session=True,
                host=self.config.lindorm_table_host,
                port=self.config.lindorm_table_port,
                user=self.config.lindorm_table_username,
                password=self.config.lindorm_table_password,
                database=self.config.lindorm_table_database,
                autocommit=False
            )
        return self.pool
    
    def initialize_tables_and_indices(self):
        """Create tables and search indices. Called during StorageManager initialization."""
        # Configure Lindorm system settings first
        self._configure_lindorm_settings()
        
        self._create_tables()
        self._create_search_indices()
    
    def _configure_lindorm_settings(self):
        """Configure Lindorm system settings for wide table operations.
        
        This method sets necessary Lindorm-specific configurations that are required
        for proper operation of wide table storage.
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Enable range delete to allow DELETE operations with partial primary keys
            # Required for deleting by user_id or project_id without specifying all PK columns
            try:
                cursor.execute("ALTER SYSTEM SET `lindorm.allow.range.delete`=TRUE")
                TRACE_LOG.info("system", "Lindorm setting configured: lindorm.allow.range.delete=TRUE")
            except Exception as e:
                # Setting might already be enabled or not supported in this Lindorm version
                TRACE_LOG.warning("system", f"Failed to set lindorm.allow.range.delete: {str(e)}")
            
            # Add other Lindorm-specific settings here as needed
            # Example:
            # try:
            #     cursor.execute("ALTER SYSTEM SET `lindorm.some.other.setting`=VALUE")
            #     TRACE_LOG.info("system", "Lindorm setting configured: lindorm.some.other.setting=VALUE")
            # except Exception as e:
            #     TRACE_LOG.warning("system", f"Failed to set lindorm.some.other.setting: {str(e)}")
            
            conn.commit()
        except Exception as e:
            TRACE_LOG.warning("system", f"Lindorm settings configuration encountered errors: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    
    def _create_tables(self):
        """Create UserEvents and UserEventsGists wide tables via SQL."""
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
        finally:
            cursor.close()
            conn.close()
    
    def _create_search_indices(self):
        """Create search indices for UserEvents and UserEventsGists tables via SQL CREATE INDEX.
        
        Lindorm automatically syncs table changes to search indices.
        No need to write directly to search indices via OpenSearch API.
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Create search index on UserEvents table
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS srh_idx USING SEARCH ON UserEvents(
                    user_id,
                    project_id,
                    event_id,
                    created_at,
                    updated_at,
                    event_data,
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
            
            # Create search index on UserEventsGists table
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS srh_idx USING SEARCH ON UserEventsGists(
                    user_id,
                    project_id,
                    event_id,
                    gist_idx,
                    created_at,
                    updated_at,
                    event_gist_data,
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
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _store_event_sync)
            return result
        except Exception as e:
            raise StorageError(f"Failed to store event: {str(e)}") from e

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
            gist_idx: Index of this gist within the event (0-based)
            gist_text: Plain text gist content (VARCHAR, not JSON)
        
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
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _store_gist_sync)
            return result
        except Exception as e:
            raise StorageError(f"Failed to store event gist: {str(e)}") from e

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
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _delete_event_sync)
            return result
        except Exception as e:
            raise StorageError(f"Failed to delete event: {str(e)}") from e

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
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _delete_gist_sync)
            return result
        except Exception as e:
            raise StorageError(f"Failed to delete event gist: {str(e)}") from e

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
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _delete_gists_sync)
            return result
        except Exception as e:
            raise StorageError(f"Failed to delete event gists: {str(e)}") from e

    async def reset(self, user_id:str, project_id: Optional[str] = None) -> Dict[str, int]:
        """Reset (delete all) events data from both UserEvents and UserEventsGists tables.
        
        Args:
            user_id: If provided, only delete data for this user. If None, delete all data.
            project_id: If provided, only delete data for this project. If None, delete all projects.
        
        Returns:
            Dictionary with counts: {"events": count, "gists": count}
        
        Note: Administrative use only. Use with caution.
        """
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                
                events_count = 0
                gists_count = 0
                
                if user_id and project_id:
                    # Delete for specific user and project
                    cursor.execute(
                        "DELETE FROM UserEvents WHERE user_id = %s AND project_id = %s",
                        (user_id, project_id)
                    )
                    events_count = cursor.rowcount
                    
                    cursor.execute(
                        "DELETE FROM UserEventsGists WHERE user_id = %s AND project_id = %s",
                        (user_id, project_id)
                    )
                    gists_count = cursor.rowcount
                elif user_id:
                    # Delete all projects for this user
                    cursor.execute(
                        "DELETE FROM UserEvents WHERE user_id = %s",
                        (user_id,)
                    )
                    events_count = cursor.rowcount
                    
                    cursor.execute(
                        "DELETE FROM UserEventsGists WHERE user_id = %s",
                        (user_id,)
                    )
                    gists_count = cursor.rowcount
                elif project_id:
                    raise ValueError("Project ID cannot be specified without user ID") 
                else:
                    cursor.execute("TRUNCATE TABLE UserEvents")
                    cursor.execute("TRUNCATE TABLE UserEventsGists")
                    events_count = -1
                    gists_count = -1
                
                conn.commit()
                return {"events": events_count, "gists": gists_count}
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            counts = await loop.run_in_executor(None, _reset_sync)
            TRACE_LOG.info(
                user_id or "system",
                f"Events reset: deleted {counts['events']} events and {counts['gists']} gists "
                f"(user_id={user_id}, project_id={project_id})"
            )
            return counts
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
            project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid vector + keyword search on UserEvents table.
        
        Args:
            project_id: Optional project filter. If None, searches across all projects.
        """
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            # Convert to milliseconds timestamp for TIMESTAMP field
            time_cutoff_ms = int(time_cutoff.timestamp() * 1000)
            
            # Build filter conditions
            filter_conditions = [
                {"term": {"_routing": user_id}},
                {"range": {"created_at": {"gte": time_cutoff_ms}}},
                {"match": {"event_data.event_tip": {"query": query}}}
            ]
            
            # Add project_id filter if specified
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})
            
            search_query = {
                "size": size,
                "sort": [{"_score": {"order": "desc"}}],
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": [{"bool": {"must": filter_conditions}}]
                                }
                            },
                            "topk": size,
                        }
                    }
                },
                "ext": {
                    "lvector": {
                        "min_score": str(min_score),
                        "hybrid_search_type": "filter_rrf",
                        "rrf_knn_weight_factor": "0.5"
                    }
                }
            }
            
            event_index_name = f"{self.config.lindorm_table_database}.UserEvents.srh_idx"
            response = self.client.search(
                index=event_index_name,
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

    async def hybrid_search_gist_events(
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
            project_id: Optional project filter. If None, searches across all projects.
        """
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            # Convert to milliseconds timestamp for TIMESTAMP field
            time_cutoff_ms = int(time_cutoff.timestamp() * 1000)
            
            # Build filter conditions
            filter_conditions = [
                {"term": {"_routing": user_id}},
                {"range": {"created_at": {"gte": time_cutoff_ms}}},
                {"match": {"event_gist_data": {"query": query}}}
            ]
            
            # Add project_id filter if specified
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})
            
            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["embedding"]
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
                        "rrf_knn_weight_factor": "0.5"
                    }
                }
            }

            
            event_gist_index_name = f"{self.config.lindorm_table_database}.UserEventsGists.srh_idx"
            response = self.client.search(
                index=event_gist_index_name,
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
    storage = get_lindorm_search_storage(config)
    return await storage.hybrid_search_gist_events(user_id, query, query_vector, topk, similarity_threshold, time_range_in_days, project_id)


async def search_user_events_with_embedding(
        user_id: str,
        query: str,
        query_vector: List[float],
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21,
        project_id: Optional[str] = None
)-> List[Dict[str, Any]]:
    storage = get_lindorm_search_storage(config)
    return await storage.hybrid_search_events(user_id, query, query_vector, topk,
                                              similarity_threshold, time_range_in_days, project_id)


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


async def store_event_gist_with_embedding(
        user_id: str,
        project_id: str,
        event_id: str,
        gist_idx: int,
        gist_text: str,
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.store_event_gist_with_embedding(user_id, project_id, event_id, gist_idx, gist_text, embedding)


async def delete_event(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> str:
    """Delete event - administrative use only."""
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event(user_id, project_id, event_id)


async def delete_event_gist(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> str:
    """Delete event gist - administrative use only."""
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event_gist(user_id, project_id, event_id)


async def delete_event_gists_by_event_id(
        user_id: str,
        project_id: str,
        event_id: str,
        config: Config = None
) -> int:
    """Delete all event gists for an event - administrative use only."""
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event_gists_by_event_id(user_id, project_id, event_id)
