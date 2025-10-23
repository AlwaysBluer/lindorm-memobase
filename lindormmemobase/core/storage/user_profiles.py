import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from mysql.connector import pooling

from ...models.response import UserProfilesData
from ...models.promise import Promise, CODE

# mysql_storage will be initialized when needed with config
lindorm_table_storage = None

def get_lindorm_table_storage(config):
    global lindorm_table_storage
    if lindorm_table_storage is None and config is None:
        raise Exception("require configuration to connect to lindorm")
    elif lindorm_table_storage is None:
        lindorm_table_storage = LindormTableStorage(config)
    return lindorm_table_storage


# class MySQLProfileStorage:
# Lindorm 宽表部分兼容Mysql协议
class LindormTableStorage:
    def __init__(self, config):
        self.config = config
        self.pool = None
        self._ensure_tables()

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
    
    def _ensure_tables(self):
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id VARCHAR(255) NOT NULL,
                    profile_id VARCHAR(255) NOT NULL,
                    content VARCHAR NOT NULL,
                    attributes JSON,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, profile_id)
                )
            """)
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def add_profiles(
        self,
        user_id: str,
        profiles: List[str],
        attributes_list: List[Dict[str, Any]]
    ) -> Promise[List[str]]:
        def _add_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            profile_ids = []
            try:
                cursor = conn.cursor()
                for content, attributes in zip(profiles, attributes_list):
                    profile_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc)
                    cursor.execute(
                        """
                        INSERT INTO user_profiles (user_id, profile_id, content, attributes, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (str(user_id), str(profile_id), str(content), json.dumps(attributes), now, now)
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
            return Promise.resolve(profile_ids)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to add profiles: {str(e)}")

    async def update_profiles(
        self,
        user_id: str,
        profile_ids: List[str],
        contents: List[str],
        attributes_list: List[Optional[Dict[str, Any]]]
    ) -> Promise[List[str]]:
        def _update_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            updated_ids = []
            
            try:
                cursor = conn.cursor()
                for profile_id, content, attributes in zip(profile_ids, contents, attributes_list):
                    now = datetime.now(timezone.utc)
                    if attributes is not None:
                        cursor.execute(
                            """
                            UPDATE user_profiles 
                            SET content = %s, attributes = %s, updated_at = %s
                            WHERE user_id = %s AND profile_id = %s
                            """,
                            (str(content), json.dumps(attributes), now, str(user_id), str(profile_id))
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE user_profiles 
                            SET content = %s, updated_at = %s
                            WHERE user_id = %s AND profile_id = %s
                            """,
                            (str(content), now, str(user_id), str(profile_id))
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
            return Promise.resolve(updated_ids)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to update profiles: {str(e)}")

    async def delete_profiles(
        self,
        user_id: str,
        profile_ids: List[str]
    ) -> Promise[int]:
        def _delete_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            try:
                cursor = conn.cursor()
                placeholders = ','.join(['%s'] * len(profile_ids))
                cursor.execute(
                    f"""
                    DELETE FROM user_profiles 
                    WHERE profile_id IN ({placeholders}) AND user_id = %s 
                    """,
                    (*[str(pid) for pid in profile_ids], str(user_id))
                )
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            deleted_count = await loop.run_in_executor(None, _delete_profiles_sync)
            return Promise.resolve(deleted_count)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to delete profiles: {str(e)}")

    async def get_user_profiles(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> Promise[List[Dict[str, Any]]]:
        def _get_profiles_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            
            try:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT profile_id, content, attributes, created_at, updated_at
                    FROM user_profiles 
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                """
                params = [user_id]
                
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                cursor.execute(query, [str(user_id)] + ([limit] if limit else []))
                results = cursor.fetchall()
                
                profiles = []
                for row in results:
                    profiles.append({
                        'id': row['profile_id'],  
                        'content': row['content'],
                        'attributes': json.loads(row['attributes']) if row['attributes'] else None,  # 解析JSON字符串
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,  
                        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None  
                    })
                return profiles
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            profiles = await loop.run_in_executor(None, _get_profiles_sync)
            return Promise.resolve(profiles)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get profiles: {str(e)}")


async def add_user_profiles(
    user_id: str, 
    profiles: List[str], 
    attributes_list: List[Dict[str, Any]],
    config
) -> Promise[List[str]]:
    storage = get_lindorm_table_storage(config)
    return await storage.add_profiles(user_id, profiles, attributes_list)

async def update_user_profiles(
    user_id: str,
    profile_ids: List[str], 
    contents: List[str], 
    attributes_list: List[Optional[Dict[str, Any]]],
    config
) -> Promise[List[str]]:
    storage = get_lindorm_table_storage(config)
    return await storage.update_profiles(user_id, profile_ids, contents, attributes_list)

async def delete_user_profiles(
    user_id: str, 
    profile_ids: List[str],
    config
) -> Promise[int]:
    storage = get_lindorm_table_storage(config)
    return await storage.delete_profiles(user_id, profile_ids)

async def get_user_profiles(user_id: str, config=None) -> Promise[UserProfilesData]:
    storage = get_lindorm_table_storage(config)
    result = await storage.get_user_profiles(user_id)
    
    if result.ok():
        profiles_data = result.data()
        return Promise.resolve(UserProfilesData(profiles=profiles_data))
    else:
        return result