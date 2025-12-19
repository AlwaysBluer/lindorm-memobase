import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch

from lindormmemobase.models.response import UserProfilesData
from lindormmemobase.utils.errors import TableStorageError
from lindormmemobase.utils.tools import validate_and_format_embedding
from lindormmemobase.config import LOG
from .base import LindormStorageBase

# Default project_id constant
DEFAULT_PROJECT_ID = "default"

# Backward compatibility - delegate to StorageManager
def get_lindorm_table_storage(config):
    """Legacy function - delegates to StorageManager."""
    from .manager import StorageManager
    return StorageManager.get_table_storage(config)


# class MySQLProfileStorage:
# Lindorm 宽表部分兼容Mysql协议
class LindormTableStorage(LindormStorageBase):
    def __init__(self, config):
        super().__init__(config)
        self.profile_index_name = f"{self.config.lindorm_table_database}.UserProfiles.srh_idx"
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
        """Return unique pool name for table storage."""
        return "memobase_pool"
    
    def _get_pool_config(self) -> dict:
        """Return connection pool configuration for table storage."""
        return {
            'host': self.config.lindorm_table_host,
            'port': self.config.lindorm_table_port,
            'user': self.config.lindorm_table_username,
            'password': self.config.lindorm_table_password,
            'database': self.config.lindorm_table_database,
            'pool_size': 10
        }
    
    def initialize_tables_and_indices(self):
        """Create UserProfiles table, indexes and search index. Called during StorageManager initialization."""
        self._create_table()
        self._create_search_index()
    
    def initialize_tables(self):
        """Legacy method - calls initialize_tables_and_indices."""
        self.initialize_tables_and_indices()
    
    def _create_table(self):
        """Create UserProfiles table via SQL."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UserProfiles (
                    user_id VARCHAR(255) NOT NULL,
                    project_id VARCHAR(255) NOT NULL,
                    profile_id VARCHAR(255) NOT NULL,
                    content VARCHAR NOT NULL,
                    topic VARCHAR(255) NOT NULL,
                    subtopic VARCHAR(255) NOT NULL,
                    update_hits INT,
                    embedding VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, project_id, profile_id)
                )
            """)
            
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON UserProfiles (created_at)
                """)
            except Exception:
                pass
            
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_updated_at ON UserProfiles (updated_at)
                """)
            except Exception:
                pass
            
            conn.commit()
            LOG.info("UserProfiles table created/verified")
        finally:
            cursor.close()
            conn.close()
    
    def _create_search_index(self):
        """Create search index for UserProfiles table with vector support."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS srh_idx USING SEARCH ON UserProfiles(
                    user_id,
                    project_id,
                    profile_id,
                    topic,
                    subtopic,
                    content(type=text,analyzer=ik,indexed=true),
                    created_at,
                    updated_at,
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
            LOG.info("UserProfiles search index created/verified")
        finally:
            cursor.close()
            conn.close()

    async def add_profiles(
        self,
        user_id: str,
        profiles: List[str],
        attributes_list: List[Dict[str, Any]],
        project_id: Optional[str] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> List[str]:
        def _add_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            profile_ids = []
            try:
                cursor = conn.cursor()
                for i, (content, attributes) in enumerate(zip(profiles, attributes_list)):
                    profile_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    
                    topic = attributes.get('topic', '')
                    subtopic = attributes.get('sub_topic', '')
                    
                    embedding_str = None
                    if embeddings is not None and i < len(embeddings):
                        embedding_str = validate_and_format_embedding(
                            embeddings[i], self.config.embedding_dim, user_id
                        )
                    
                    cursor.execute(
                        """
                        INSERT INTO UserProfiles 
                        (user_id, project_id, profile_id, content, topic, subtopic, update_hits, embedding, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (str(user_id), str(actual_project_id), str(profile_id), 
                         str(content), str(topic), str(subtopic), 0, embedding_str, now, now)
                    )
                    profile_ids.append(profile_id)
                conn.commit()
                return profile_ids
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _add_profiles_sync,
            "Failed to add profiles"
        )

    async def update_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        contents: List[str],
        attributes_list: List[Optional[Dict[str, Any]]],
        project_id: Optional[str] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> List[str]:
        def _update_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            updated_ids = []
            
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor(dictionary=True)
                for i, (profile_id, content, attributes) in enumerate(zip(profile_ids, contents, attributes_list)):
                    now = datetime.now(timezone.utc)
                    
                    if attributes is not None and 'update_hits' in attributes:
                        new_update_hits = attributes['update_hits']
                    else:
                        new_update_hits = 0
                    
                    embedding_str = None
                    if embeddings is not None and i < len(embeddings):
                        embedding_str = validate_and_format_embedding(
                            embeddings[i], self.config.embedding_dim, user_id
                        )
                    
                    if attributes is not None:
                        topic = attributes.get('topic', '')
                        subtopic = attributes.get('sub_topic', '')
                        
                        if embedding_str is not None:
                            cursor.execute(
                                """
                                UPDATE UserProfiles 
                                SET content = %s, topic = %s, subtopic = %s, update_hits = %s, embedding = %s, updated_at = %s
                                WHERE user_id = %s AND project_id = %s AND profile_id = %s
                                """,
                                (str(content), str(topic), str(subtopic), new_update_hits, embedding_str, now, str(user_id), str(actual_project_id), str(profile_id))
                            )
                        else:
                            cursor.execute(
                                """
                                UPDATE UserProfiles 
                                SET content = %s, topic = %s, subtopic = %s, update_hits = %s, updated_at = %s
                                WHERE user_id = %s AND project_id = %s AND profile_id = %s
                                """,
                                (str(content), str(topic), str(subtopic), new_update_hits, now, str(user_id), str(actual_project_id), str(profile_id))
                            )
                    else:
                        if embedding_str is not None:
                            cursor.execute(
                                """
                                UPDATE UserProfiles 
                                SET content = %s, update_hits = %s, embedding = %s, updated_at = %s
                                WHERE user_id = %s AND project_id = %s AND profile_id = %s
                                """,
                                (str(content), new_update_hits, embedding_str, now, str(user_id), str(actual_project_id), str(profile_id))
                            )
                        else:
                            cursor.execute(
                                """
                                UPDATE UserProfiles 
                                SET content = %s, update_hits = %s, updated_at = %s
                                WHERE user_id = %s AND project_id = %s AND profile_id = %s
                                """,
                                (str(content), new_update_hits, now, str(user_id), str(actual_project_id), str(profile_id))
                            )
                    
                    if cursor.rowcount > 0:
                        updated_ids.append(profile_id)
                
                conn.commit()
                return updated_ids
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _update_profiles_sync,
            "Failed to update profiles"
        )

    async def delete_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        project_id: Optional[str] = None
    ) -> int:
        def _delete_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            try:
                cursor = conn.cursor()
                deleted_count = 0
                
                # Lindorm requires all PK columns for delete operations
                # Must delete one row at a time to avoid "range delete" error
                if project_id is not None:
                    # Delete from specific project - one row at a time
                    for profile_id in profile_ids:
                        cursor.execute(
                            """
                            DELETE FROM UserProfiles 
                            WHERE user_id = %s AND project_id = %s AND profile_id = %s
                            """,
                            (str(user_id), str(project_id), str(profile_id))
                        )
                        deleted_count += cursor.rowcount
                else:
                    # When project_id is None, we need to fetch the project_id for each profile first
                    # This is for backward compatibility but should be avoided
                    for profile_id in profile_ids:
                        # First, get the project_id for this profile
                        cursor.execute(
                            """
                            SELECT project_id FROM UserProfiles
                            WHERE user_id = %s AND profile_id = %s
                            LIMIT 1
                            """,
                            (str(user_id), str(profile_id))
                        )
                        result = cursor.fetchone()
                        if result:
                            actual_project_id = result[0]
                            # Now delete with all PK columns
                            cursor.execute(
                                """
                                DELETE FROM UserProfiles 
                                WHERE user_id = %s AND project_id = %s AND profile_id = %s
                                """,
                                (str(user_id), str(actual_project_id), str(profile_id))
                            )
                            deleted_count += cursor.rowcount
                
                conn.commit()
                return deleted_count
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _delete_profiles_sync,
            "Failed to delete profiles"
        )

    async def get_user_profiles(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        def _get_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            try:
                cursor = conn.cursor(dictionary=True)
                
                # Build query with filters
                query = """
                    SELECT profile_id, content, topic, subtopic, update_hits, created_at, updated_at, project_id
                    FROM UserProfiles 
                    WHERE user_id = %s
                """
                params = [str(user_id)]
                
                # Add project_id filter if specified
                if project_id is not None:
                    query += " AND project_id = %s"
                    params.append(str(project_id))
                
                # Add time range filters if specified
                if time_from is not None:
                    query += " AND created_at >= %s"
                    params.append(time_from)
                
                if time_to is not None:
                    query += " AND created_at <= %s"
                    params.append(time_to)
                
                query += " ORDER BY updated_at DESC"
                
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                profiles = []
                for row in results:
                    # In-memory filtering for topics and subtopics
                    if topics and row['topic'] not in topics:
                        continue
                    if subtopics and row['subtopic'] not in subtopics:
                        continue
                    
                    # Reconstruct attributes dict from topic and subtopic columns
                    profiles.append({
                        'id': row['profile_id'],  
                        'content': row['content'],
                        'attributes': {
                            'topic': row['topic'],
                            'sub_topic': row['subtopic'],
                            'update_hits': row.get('update_hits', 0),
                        },
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,  
                        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                        'project_id': row.get('project_id', DEFAULT_PROJECT_ID)
                    })
                return profiles
            finally:
                cursor.close()
                conn.close()
        
        return await self._execute_sync_operation(
            _get_profiles_sync,
            "Failed to get profiles"
        )

    async def reset(self, user_id: Optional[str] = None, project_id: Optional[str] = None) -> int:
        """Reset (delete all) user profiles data.
        
        Args:
            user_id: If provided, only delete data for this user. If None, delete all data.
            project_id: If provided, only delete data for this project. If None, delete all projects.
        
        Returns:
            Number of rows deleted
        
        Note: Administrative use only. Use with caution.
        """
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                
                if user_id and project_id:
                    cursor.execute(
                        "DELETE FROM UserProfiles WHERE user_id = %s AND project_id = %s",
                        (user_id, project_id)
                    )
                elif user_id:
                    cursor.execute(
                        "DELETE FROM UserProfiles WHERE user_id = %s",
                        (user_id,)
                    )
                elif project_id:
                    raise ValueError("Project ID cannot be specified without user ID") 
                else:
                    # Delete all data (use TRUNCATE for better performance)
                    cursor.execute("TRUNCATE TABLE UserProfiles")
                    # TRUNCATE doesn't return rowcount, return -1 to indicate full reset
                    conn.commit()
                    return -1
                
                affected_rows = cursor.rowcount
                conn.commit()
                return affected_rows
            except Exception as e:
                raise
            finally:
                cursor.close()
                conn.close()
        
        try:
            # Use base class helper method instead of manual executor pattern
            count = await self._execute_sync_operation(
                _reset_sync,
                "Failed to reset user profiles"
            )
            LOG.info(f"User profiles reset: deleted {count} rows (user_id={user_id}, project_id={project_id})")
            return count
        except Exception as e:
            raise TableStorageError(f"Failed to reset user profiles: {str(e)}") from e

    async def vector_search_profiles(
        self,
        user_id: str,
        query: str,
        query_vector: List[float],
        size: int = 10,
        min_score: float = 0.5,
        project_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        subtopics: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Vector search on UserProfiles using embedding similarity.
        
        Args:
            user_id: User identifier
            query: Text query for keyword matching
            query_vector: Query embedding vector
            size: Maximum number of results
            min_score: Minimum similarity score
            project_id: Optional project filter
            topics: Filter by topic (OR logic)
            subtopics: Filter by subtopic (OR logic)
        
        Returns:
            List of matching profiles with similarity scores
        """
        from lindormmemobase.utils.errors import SearchStorageError
        
        try:
            filter_conditions = [
                {"term": {"user_id": user_id}},
                {"match": {"content": {"query": query}}}
            ]
            
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})
            
            if topics:
                filter_conditions.append({
                    "terms": {"topic": topics}
                })
            
            if subtopics:
                filter_conditions.append({
                    "terms": {"subtopic": subtopics}
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
                        "rrf_knn_weight_factor": "0.6",
                        "client_refactor": "true",
                        "rrf_rank_constant": "2"
                    }
                }
            }
            
            response = self.client.search(
                index=self.profile_index_name,
                body=search_query,
                routing=user_id
            )

            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    'id': source.get('profile_id', hit['_id']),
                    'content': source.get('content', ''),
                    'attributes': {
                        'topic': source.get('topic', ''),
                        'sub_topic': source.get('subtopic', ''),
                        'update_hits': source.get('update_hits', 0),
                    },
                    'created_at': source.get('created_at'),
                    'updated_at': source.get('updated_at'),
                    'similarity': hit['_score'],
                    'project_id': source.get('project_id', DEFAULT_PROJECT_ID)
                })

            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to vector search profiles: {str(e)}") from e


async def add_user_profiles(
    user_id: str, 
    profiles: List[str], 
    attributes_list: List[Dict[str, Any]],
    config,
    project_id: Optional[str] = None
) -> List[str]:
    embeddings = None
    if config.enable_profile_embedding and profiles:
        from lindormmemobase.embedding import get_embedding
        embeddings_arr = await get_embedding(profiles, phase="document", config=config)
        embeddings = [e.tolist() for e in embeddings_arr]
    
    storage = get_lindorm_table_storage(config)
    return await storage.add_profiles(user_id, profiles, attributes_list, project_id, embeddings)

async def update_user_profiles(
    user_id: str,
    profile_ids: List[str], 
    contents: List[str], 
    attributes_list: List[Optional[Dict[str, Any]]],
    config,
    project_id: Optional[str] = None
) -> List[str]:
    embeddings = None
    if config.enable_profile_embedding and contents:
        from lindormmemobase.embedding import get_embedding
        embeddings_arr = await get_embedding(contents, phase="document", config=config)
        embeddings = [e.tolist() for e in embeddings_arr]
    
    storage = get_lindorm_table_storage(config)
    return await storage.update_profiles(user_id, profile_ids, contents, attributes_list, project_id, embeddings)

async def delete_user_profiles(
    user_id: str, 
    profile_ids: List[str],
    config,
    project_id: Optional[str] = None
) -> int:
    storage = get_lindorm_table_storage(config)
    return await storage.delete_profiles(user_id, profile_ids, project_id)

async def get_user_profiles(
    user_id: str, 
    config=None,
    project_id: Optional[str] = None,
    topics: Optional[List[str]] = None,
    subtopics: Optional[List[str]] = None,
    time_from: Optional[datetime] = None,
    time_to: Optional[datetime] = None
) -> UserProfilesData:
    storage = get_lindorm_table_storage(config)
    profiles_data = await storage.get_user_profiles(user_id, project_id, topics, subtopics, time_from, time_to)
    return UserProfilesData(profiles=profiles_data)