import json
import threading
from datetime import datetime
from typing import Callable, Awaitable, List, Optional, Tuple
from mysql.connector import pooling, MySQLConnection
from contextlib import contextmanager

from ...config import TRACE_LOG, Config
from ..constants import BufferStatus
from ...models.blob import BlobType, Blob
from ...models.promise import Promise, CODE
from ...models.response import ChatModalResponse
from ...models.profile_topic import ProfileConfig

from ...utils.tools import get_blob_token_size
from ...core.extraction.processor.process_blobs import process_blobs

BlobProcessFunc = Callable[
    [str, Optional[ProfileConfig], list[Blob], Config],
    Awaitable[Promise[ChatModalResponse]],
]

BLOBS_PROCESS: dict[BlobType, BlobProcessFunc] = {BlobType.chat: process_blobs}


class LindormBufferStorage:
    def __init__(self, config: Config):
        self.config = config
        self._pool = None
        self._ensure_tables()
    
    @property
    def pool(self) -> pooling.MySQLConnectionPool:
        if self._pool is None:
            host = self.config.lindorm_buffer_host or self.config.lindorm_table_host
            port = self.config.lindorm_buffer_port or self.config.lindorm_table_port
            username = self.config.lindorm_buffer_username or self.config.lindorm_table_username
            password = self.config.lindorm_buffer_password or self.config.lindorm_table_password
            database = self.config.lindorm_buffer_database or self.config.lindorm_table_database
            
            self._pool = pooling.MySQLConnectionPool(
                pool_name="buffer_pool",
                pool_size=10,
                pool_reset_session=True,
                host=host,
                port=port,
                user=username,
                password=password,
                database=database,
                autocommit=False
            )
        return self._pool
    
    @contextmanager
    def get_connection(self):
        conn = None
        cursor = None
        try:
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            yield conn, cursor
        except Exception:
            if conn:
                conn.rollback()
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _ensure_tables(self):
        with self.get_connection() as (conn, cursor):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS buffer (
                    user_id VARCHAR(255) NOT NULL,
                    blob_id VARCHAR(255) NOT NULL,
                    blob_type VARCHAR(50) NOT NULL,
                    blob_data VARCHAR(65535) NOT NULL,
                    token_size INT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    created_at BIGINT NOT NULL,
                    updated_at BIGINT NOT NULL,
                    PRIMARY KEY(user_id, blob_id)
                )
            """)

    def insert_blob(self, user_id: str, blob_id: str, blob_data: Blob) -> Promise[None]:
        try:
            now = int(datetime.now().timestamp())
            with self.get_connection() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO buffer (user_id, blob_id, blob_type, blob_data, token_size, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (user_id, blob_id, blob_data.type.value, json.dumps(blob_data.model_dump(), default=str), get_blob_token_size(blob_data), BufferStatus.idle, now, now)
                )
            return Promise.resolve(None)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to insert blob: {str(e)}")

    def get_capacity(self, user_id: str, blob_type: BlobType) -> Promise[int]:
        try:
            with self.get_connection() as (conn, cursor):
                cursor.execute(
                    "SELECT COUNT(*) FROM buffer WHERE user_id = %s AND blob_type = %s AND status = %s",
                    (user_id, blob_type.value, BufferStatus.idle)
                )
                return Promise.resolve(cursor.fetchone()[0])
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get capacity: {str(e)}")
    
    def get_pending_ids(self, user_id: str, blob_type: BlobType, status: str = BufferStatus.idle) -> Promise[List[str]]:
        try:
            with self.get_connection() as (conn, cursor):
                cursor.execute(
                    "SELECT blob_id FROM buffer WHERE user_id = %s AND blob_type = %s AND status = %s ORDER BY created_at",
                    (user_id, blob_type.value, status)
                )
                return Promise.resolve([row[0] for row in cursor.fetchall()])
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get pending ids: {str(e)}")

    def check_overflow(self, user_id: str, blob_type: BlobType, max_tokens: int) -> Promise[List[str]]:
        try:
            with self.get_connection() as (conn, cursor):
                cursor.execute(
                    "SELECT blob_id, token_size FROM buffer WHERE user_id = %s AND blob_type = %s AND status = %s ORDER BY created_at",
                    (user_id, blob_type.value, BufferStatus.idle)
                )
                results = cursor.fetchall()
                
                if not results:
                    return Promise.resolve([])
                
                total_tokens = sum(row[1] for row in results)
                if total_tokens > max_tokens:
                    TRACE_LOG.info(user_id, f"Buffer overflow: {total_tokens} > {max_tokens}")
                    return Promise.resolve([row[0] for row in results])
                
                return Promise.resolve([])
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to check overflow: {str(e)}")

    def _load_blobs(self, user_id: str, blob_ids: List[str]) -> List[Tuple[Blob, str]]:
        with self.get_connection() as (conn, cursor):
            placeholders = ','.join(['%s'] * len(blob_ids))
            cursor.execute(
                f"SELECT blob_id, blob_type, blob_data FROM buffer WHERE user_id = %s AND blob_id IN ({placeholders}) ORDER BY created_at",
                [user_id] + blob_ids
            )
            
            blobs = []
            for blob_id, blob_type_str, blob_data_json in cursor.fetchall():
                blob_data = json.loads(blob_data_json)
                blob_type = BlobType(blob_type_str)
                
                if blob_type == BlobType.chat:
                    from ...models.blob import ChatBlob
                    blob = ChatBlob(**blob_data)
                elif blob_type == BlobType.doc:
                    from ...models.blob import DocBlob
                    blob = DocBlob(**blob_data)
                elif blob_type == BlobType.code:
                    from ...models.blob import CodeBlob
                    blob = CodeBlob(**blob_data)
                else:
                    raise ValueError(f"Unsupported blob type: {blob_type}")
                
                blobs.append((blob, blob_id))
            
            return blobs
    
    def _update_status(self, user_id: str, blob_ids: List[str], status: str):
        now = int(datetime.now().timestamp())
        with self.get_connection() as (conn, cursor):
            for blob_id in blob_ids:
                cursor.execute(
                    "UPDATE buffer SET status = %s, updated_at = %s WHERE user_id = %s AND blob_id = %s",
                    (status, now, user_id, blob_id)
                )

    async def flush(self, user_id: str, blob_type: BlobType, blob_ids: List[str], 
                   status: str = BufferStatus.idle, profile_config=None) -> Promise[ChatModalResponse | None]:
        if blob_type not in BLOBS_PROCESS or not blob_ids:
            return Promise.resolve(None)
        
        try:
            # Load blobs
            blobs_with_ids = self._load_blobs(user_id, blob_ids)
            if not blobs_with_ids:
                return Promise.resolve(None)
            
            blobs = [blob for blob, _ in blobs_with_ids]
            actual_blob_ids = [blob_id for _, blob_id in blobs_with_ids]
            
            # Update to processing
            if status != BufferStatus.processing:
                self._update_status(user_id, actual_blob_ids, BufferStatus.processing)
            
            TRACE_LOG.info(user_id, f"Processing {len(blobs)} {blob_type} blobs")
            
            # Process
            result = await BLOBS_PROCESS[blob_type](user_id, profile_config, blobs, self.config)
            
            # Update final status
            final_status = BufferStatus.done if result.ok() else BufferStatus.failed
            self._update_status(user_id, actual_blob_ids, final_status)
            
            return result
        
        except Exception as e:
            TRACE_LOG.error(user_id, f"Flush error: {e}")
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Flush failed: {str(e)}")


# Global singleton storage cache
_storage_cache = {}
_storage_lock = threading.Lock()

# Public API - singleton pattern with cache
def create_buffer_storage(config: Config) -> LindormBufferStorage:
    # Create cache key based on connection parameters
    cache_key = (
        config.lindorm_buffer_host or config.lindorm_table_host,
        config.lindorm_buffer_port or config.lindorm_table_port,
        config.lindorm_buffer_username or config.lindorm_table_username,
        config.lindorm_buffer_database or config.lindorm_table_database
    )
    
    # Thread-safe singleton creation
    with _storage_lock:
        if cache_key not in _storage_cache:
            _storage_cache[cache_key] = LindormBufferStorage(config)
        return _storage_cache[cache_key]


def clear_buffer_storage_cache():
    """Clear the storage cache. Useful for testing or cleanup."""
    global _storage_cache
    with _storage_lock:
        # Close existing connections if possible
        for storage in _storage_cache.values():
            try:
                if hasattr(storage, '_pool') and storage._pool:
                    storage._pool.close()
            except:
                pass  # Ignore cleanup errors
        _storage_cache.clear()


async def insert_blob_to_buffer(user_id: str, blob_id: str, blob_data: Blob, config: Config) -> Promise[None]:
    storage = create_buffer_storage(config)
    return storage.insert_blob(user_id, blob_id, blob_data)


async def get_buffer_capacity(user_id: str, blob_type: BlobType, config: Config) -> Promise[int]:
    storage = create_buffer_storage(config)
    return storage.get_capacity(user_id, blob_type)


async def detect_buffer_full_or_not(user_id: str, blob_type: BlobType, config: Config) -> Promise[List[str]]:
    storage = create_buffer_storage(config)
    return storage.check_overflow(user_id, blob_type, config.max_chat_blob_buffer_token_size)


async def get_unprocessed_buffer_ids(user_id: str, blob_type: BlobType, config: Config, select_status: str = BufferStatus.idle) -> Promise[List[str]]:
    storage = create_buffer_storage(config)
    return storage.get_pending_ids(user_id, blob_type, select_status)


async def flush_buffer_by_ids(user_id: str, blob_type: BlobType, buffer_ids: List[str], config: Config, 
                             select_status: str = BufferStatus.idle, profile_config=None) -> Promise[ChatModalResponse | None]:
    storage = create_buffer_storage(config)
    return await storage.flush(user_id, blob_type, buffer_ids, select_status, profile_config)


async def wait_insert_done_then_flush(user_id: str, blob_type: BlobType, config: Config, profile_config=None) -> Promise[ChatModalResponse | None]:
    storage = create_buffer_storage(config)
    p = storage.get_pending_ids(user_id, blob_type)
    if not p.ok():
        return p
    
    buffer_ids = p.data()
    if not buffer_ids:
        return Promise.resolve(None)
    
    return await storage.flush(user_id, blob_type, buffer_ids, BufferStatus.idle, profile_config)


async def flush_buffer(user_id: str, blob_type: BlobType, config: Config, profile_config=None) -> Promise[ChatModalResponse | None]:
    storage = create_buffer_storage(config)
    p = storage.get_pending_ids(user_id, blob_type)
    if not p.ok():
        return p
    
    buffer_ids = p.data()
    if not buffer_ids:
        return Promise.resolve(None)
    
    return await storage.flush(user_id, blob_type, buffer_ids, BufferStatus.idle, profile_config)