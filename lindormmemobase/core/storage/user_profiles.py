import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from mysql.connector import pooling

from ...models.response import UserProfilesData
from ...utils.errors import TableStorageError

# Default project_id constant
DEFAULT_PROJECT_ID = "default"

# Backward compatibility - delegate to StorageManager
def get_lindorm_table_storage(config):
    """Legacy function - delegates to StorageManager."""
    from .manager import StorageManager
    return StorageManager.get_table_storage(config)


# class MySQLProfileStorage:
# Lindorm 宽表部分兼容Mysql协议
class LindormTableStorage:
    def __init__(self, config):
        self.config = config
        self.pool = None
        # Don't call _ensure_tables in __init__ anymore
        # Tables are created explicitly via initialize_tables()

    def _get_pool(self):
        if self.pool is None:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="memobase_pool",
                pool_size=10,
                pool_reset_session=True,
                host=self.config.lindorm_table_host,
                port=self.config.lindorm_table_port,
                user=self.config.lindorm_table_username,
                password=self.config.lindorm_table_password,
                database=self.config.lindorm_table_database,
                autocommit=False
            )
        return self.pool
    
    def initialize_tables(self):
        """Create UserProfilesV2 table and indexes. Called during StorageManager initialization."""
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            # Create UserProfilesV2 table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UserProfilesV2 (
                    user_id VARCHAR(255) NOT NULL,
                    project_id VARCHAR(255) NOT NULL,
                    profile_id VARCHAR(255) NOT NULL,
                    content VARCHAR NOT NULL,
                    topic VARCHAR(255) NOT NULL,
                    subtopic VARCHAR(255) NOT NULL,
                    update_hits INT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, project_id, profile_id)
                )
            """)
            
            # Create secondary indexes for time-based queries
            # Note: Lindorm/MySQL may require specific syntax for index creation
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON UserProfilesV2 (created_at)
                """)
            except Exception:
                # Index might already exist or syntax not supported
                pass
            
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_updated_at ON UserProfilesV2 (updated_at)
                """)
            except Exception:
                # Index might already exist or syntax not supported  
                pass
            
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def add_profiles(
        self,
        user_id: str,
        profiles: List[str],
        attributes_list: List[Dict[str, Any]],
        project_id: Optional[str] = None
    ) -> List[str]:
        def _add_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            # Use default project_id if not provided
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            profile_ids = []
            try:
                cursor = conn.cursor()
                for content, attributes in zip(profiles, attributes_list):
                    profile_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    
                    # Extract topic and subtopic from attributes
                    topic = attributes.get('topic', '')
                    subtopic = attributes.get('sub_topic', '')
                    
                    cursor.execute(
                        """
                        INSERT INTO UserProfilesV2 
                        (user_id, project_id, profile_id, content, topic, subtopic, update_hits, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (str(user_id), str(actual_project_id), str(profile_id), 
                         str(content), str(topic), str(subtopic), 0, now, now)
                    )
                    profile_ids.append(profile_id)
                conn.commit()
                return profile_ids
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            profile_ids = await loop.run_in_executor(None, _add_profiles_sync)
            return profile_ids
        except Exception as e:
            raise TableStorageError(f"Failed to add profiles: {str(e)}") from e

    async def update_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        contents: List[str],
        attributes_list: List[Optional[Dict[str, Any]]],
        project_id: Optional[str] = None
    ) -> List[str]:
        def _update_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            updated_ids = []
            
            # Use default project_id if not provided
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            
            try:
                cursor = conn.cursor(dictionary=True)
                for profile_id, content, attributes in zip(profile_ids, contents, attributes_list):
                    now = datetime.now(timezone.utc)
                    
                    # Determine update_hits value
                    # If attributes contains update_hits, use it (already incremented in merge.py)
                    # Otherwise, fetch current value and increment by 1
                    if attributes is not None and 'update_hits' in attributes:
                        new_update_hits = attributes['update_hits']
                    else:
                        # Fetch current update_hits value
                        new_update_hits = 0
                    if attributes is not None:
                        # Extract topic and subtopic from attributes
                        topic = attributes.get('topic', '')
                        subtopic = attributes.get('sub_topic', '')
                        
                        cursor.execute(
                            """
                            UPDATE UserProfilesV2 
                            SET content = %s, topic = %s, subtopic = %s, update_hits = %s, updated_at = %s
                            WHERE user_id = %s AND project_id = %s AND profile_id = %s
                            """,
                            (str(content), str(topic), str(subtopic), new_update_hits, now, str(user_id), str(actual_project_id), str(profile_id))
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE UserProfilesV2 
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
        
        try:
            loop = asyncio.get_event_loop()
            updated_ids = await loop.run_in_executor(None, _update_profiles_sync)
            return updated_ids
        except Exception as e:
            raise TableStorageError(f"Failed to update profiles: {str(e)}") from e

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
                            DELETE FROM UserProfilesV2 
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
                            SELECT project_id FROM UserProfilesV2
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
                                DELETE FROM UserProfilesV2 
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
        
        try:
            loop = asyncio.get_event_loop()
            deleted_count = await loop.run_in_executor(None, _delete_profiles_sync)
            return deleted_count
        except Exception as e:
            raise TableStorageError(f"Failed to delete profiles: {str(e)}") from e

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
                    FROM UserProfilesV2 
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
        
        try:
            loop = asyncio.get_event_loop()
            profiles = await loop.run_in_executor(None, _get_profiles_sync)
            return profiles
        except Exception as e:
            raise TableStorageError(f"Failed to get profiles: {str(e)}") from e


async def add_user_profiles(
    user_id: str, 
    profiles: List[str], 
    attributes_list: List[Dict[str, Any]],
    config,
    project_id: Optional[str] = None
) -> List[str]:
    storage = get_lindorm_table_storage(config)
    return await storage.add_profiles(user_id, profiles, attributes_list, project_id)

async def update_user_profiles(
    user_id: str,
    profile_ids: List[str], 
    contents: List[str], 
    attributes_list: List[Optional[Dict[str, Any]]],
    config,
    project_id: Optional[str] = None
) -> List[str]:
    storage = get_lindorm_table_storage(config)
    return await storage.update_profiles(user_id, profile_ids, contents, attributes_list, project_id)

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