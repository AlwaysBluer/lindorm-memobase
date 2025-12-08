import asyncio
import json
from datetime import datetime
from typing import Callable, Awaitable, List, Optional, Tuple
from mysql.connector import pooling

from ...config import TRACE_LOG, Config
from ..constants import BufferStatus
from ...models.blob import BlobType, Blob
from ...utils.errors import BufferStorageError
from ...models.response import ChatModalResponse
from ...models.profile_topic import ProfileConfig
from .user_profiles import DEFAULT_PROJECT_ID

from ...utils.tools import get_blob_token_size
from ..extraction.processor.process_blobs import process_blobs

BlobProcessFunc = Callable[
    [str, Optional[ProfileConfig], list[Blob], Config],
    Awaitable[ChatModalResponse],
]

BLOBS_PROCESS: dict[BlobType, BlobProcessFunc] = {BlobType.chat: process_blobs}


class LindormBufferStorage:
    def __init__(self, config: Config):
        self.config = config
        self._pool = None
        # Don't call _ensure_tables in __init__ anymore
        # Tables are created explicitly via initialize_tables()
    
    def initialize_tables(self):
        """Create BufferStorage table. Called during StorageManager initialization."""
        def _init_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS BufferStorage (
                        user_id VARCHAR(255) NOT NULL,
                        project_id VARCHAR(255) NOT NULL,
                        blob_id VARCHAR(255) NOT NULL,
                        blob_type VARCHAR(50) NOT NULL,
                        blob_data VARCHAR(65535) NOT NULL,
                        token_size INT NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        created_at BIGINT NOT NULL,
                        updated_at BIGINT NOT NULL,
                        PRIMARY KEY(user_id, project_id, blob_id)
                    )
                """)
                conn.commit()
            finally:
                cursor.close()
                conn.close()
        
        _init_sync()

    def _get_pool(self) -> pooling.MySQLConnectionPool:
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

    async def insert_blob(self, user_id: str, blob_id: str, blob_data: Blob, project_id: Optional[str] = None) -> None:
        def _insert_sync():
            actual_project_id = project_id or self.config.default_project_id or DEFAULT_PROJECT_ID
            now = int(datetime.now().timestamp())
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO BufferStorage (user_id, project_id, blob_id, blob_type, blob_data, token_size, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (user_id, actual_project_id, blob_id, blob_data.type.value, json.dumps(blob_data.model_dump(), default=str),
                     get_blob_token_size(blob_data), BufferStatus.idle, now, now)
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _insert_sync)
        except Exception as e:
            raise BufferStorageError(f"Failed to insert blob: {str(e)}") from e

    async def get_capacity(self, user_id: str, blob_type: BlobType, project_id: Optional[str] = None) -> int:
        def _get_capacity_sync():
            actual_project_id = project_id or self.config.default_project_id or DEFAULT_PROJECT_ID
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM BufferStorage WHERE user_id = %s AND project_id = %s AND blob_type = %s AND status = %s",
                    (user_id, actual_project_id, blob_type.value, BufferStatus.idle)
                )
                result = cursor.fetchone()[0]
                conn.commit()
                return result
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(None, _get_capacity_sync)
            return count
        except Exception as e:
            raise BufferStorageError(f"Failed to get capacity: {str(e)}") from e

    async def get_ids_by_status(self, user_id: str, blob_type: BlobType, status: str = BufferStatus.idle, project_id: Optional[str] = None) -> List[str]:
        def _get_ids_sync():
            actual_project_id = project_id or self.config.default_project_id or DEFAULT_PROJECT_ID
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT blob_id FROM BufferStorage WHERE user_id = %s AND project_id = %s AND blob_type = %s AND status = %s ORDER BY created_at",
                    (user_id, actual_project_id, blob_type.value, status)
                )
                result = [row[0] for row in cursor.fetchall()]
                conn.commit()
                return result
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            blob_ids = await loop.run_in_executor(None, _get_ids_sync)
            return blob_ids
        except Exception as e:
            raise BufferStorageError(f"Failed to get pending ids: {str(e)}") from e

    async def check_overflow(self, user_id: str, blob_type: BlobType, max_tokens: int, project_id: Optional[str] = None) -> List[str]:
        def _check_overflow_sync():
            actual_project_id = project_id or self.config.default_project_id or DEFAULT_PROJECT_ID
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT blob_id, token_size FROM BufferStorage WHERE user_id = %s AND project_id = %s AND blob_type = %s AND status = %s ORDER BY created_at",
                    (user_id, actual_project_id, blob_type.value, BufferStatus.idle)
                )
                results = cursor.fetchall()
                conn.commit()

                if not results:
                    return []

                total_tokens = sum(row[1] for row in results)
                if total_tokens > max_tokens:
                    TRACE_LOG.info(user_id, f"Buffer overflow: {total_tokens} > {max_tokens}")
                    return [row[0] for row in results]

                return []
            finally:
                cursor.close()
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            blob_ids = await loop.run_in_executor(None, _check_overflow_sync)
            return blob_ids
        except Exception as e:
            raise BufferStorageError(f"Failed to check overflow: {str(e)}") from e

    async def _load_blobs(self, user_id: str, blob_ids: List[str], project_id: str) -> List[Tuple[Blob, str]]:
        def _load_blobs_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                placeholders = ','.join(['%s'] * len(blob_ids))
                cursor.execute(
                    f"SELECT blob_id, blob_type, blob_data FROM BufferStorage WHERE user_id = %s AND project_id = %s AND blob_id IN ({placeholders}) ORDER BY created_at",
                    [user_id, project_id] + blob_ids
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
                
                conn.commit()
                return blobs
            finally:
                cursor.close()
                conn.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load_blobs_sync)

    async def _update_status(self, user_id: str, blob_ids: List[str], status: str, project_id: str):
        """Update status for multiple blobs using batch UPDATE with IN clause."""
        def _update_status_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            now = int(datetime.now().timestamp())
            try:
                cursor = conn.cursor()
                # Use batch UPDATE with IN clause for better performance
                if blob_ids:
                    placeholders = ','.join(['%s'] * len(blob_ids))
                    cursor.execute(
                        f"UPDATE BufferStorage SET status = %s, updated_at = %s WHERE user_id = %s AND project_id = %s AND blob_id IN ({placeholders})",
                        [status, now, user_id, project_id] + blob_ids
                    )
                conn.commit()
            finally:
                cursor.close()
                conn.close()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _update_status_sync)

    async def flush(self, user_id: str, blob_type: BlobType, blob_ids: List[str],
                    status: str = BufferStatus.idle, profile_config=None, project_id: Optional[str] = None) -> Optional[ChatModalResponse]:
        if blob_type not in BLOBS_PROCESS or not blob_ids:
            return None

        try:
            actual_project_id = project_id or self.config.default_project_id or DEFAULT_PROJECT_ID
            
            # Load blobs
            blobs_with_ids = await self._load_blobs(user_id, blob_ids, actual_project_id)
            if not blobs_with_ids:
                return None

            blobs = [blob for blob, _ in blobs_with_ids]
            actual_blob_ids = [blob_id for _, blob_id in blobs_with_ids]

            # Update to processing
            if status != BufferStatus.processing:
                await self._update_status(user_id, actual_blob_ids, BufferStatus.processing, actual_project_id)

            TRACE_LOG.info(user_id, f"Processing {len(blobs)} {blob_type} blobs")

            # Process
            result = await BLOBS_PROCESS[blob_type](user_id, profile_config, blobs, self.config, actual_project_id)

            # Update final status
            await self._update_status(user_id, actual_blob_ids, BufferStatus.done, actual_project_id)

            return result

        except Exception as e:
            TRACE_LOG.error(user_id, f"Flush error: {e}")
            # Mark as failed if possible
            if 'actual_blob_ids' in locals():
                try:
                    await self._update_status(user_id, actual_blob_ids, BufferStatus.failed, actual_project_id)
                except:
                    pass
            raise BufferStorageError(f"Flush failed: {str(e)}") from e


# Backward compatibility - delegate to StorageManager
def create_buffer_storage(config: Config) -> LindormBufferStorage:
    """Create or get cached buffer storage - delegates to StorageManager."""
    from .manager import StorageManager
    return StorageManager.get_buffer_storage(config)


def clear_buffer_storage_cache():
    """Clear the storage cache. Useful for testing or cleanup - delegates to StorageManager."""
    from .manager import StorageManager
    StorageManager.cleanup()


async def insert_blob_to_buffer(user_id: str, blob_id: str, blob_data: Blob, config: Config, project_id: Optional[str] = None) -> None:
    storage = create_buffer_storage(config)
    return await storage.insert_blob(user_id, blob_id, blob_data, project_id)


async def get_buffer_capacity(user_id: str, blob_type: BlobType, config: Config, project_id: Optional[str] = None) -> int:
    storage = create_buffer_storage(config)
    return await storage.get_capacity(user_id, blob_type, project_id)


async def detect_buffer_full_or_not(user_id: str, blob_type: BlobType, config: Config, project_id: Optional[str] = None) -> List[str]:
    storage = create_buffer_storage(config)
    return await storage.check_overflow(user_id, blob_type, config.max_chat_blob_buffer_token_size, project_id)


async def get_unprocessed_buffer_ids(user_id: str, blob_type: BlobType, config: Config,
                                     select_status: str = BufferStatus.idle, project_id: Optional[str] = None) -> List[str]:
    storage = create_buffer_storage(config)
    return await storage.get_ids_by_status(user_id, blob_type, select_status, project_id)


async def flush_buffer_by_ids(user_id: str, blob_type: BlobType, buffer_ids: List[str], config: Config,
                              select_status: str = BufferStatus.idle, profile_config=None, project_id: Optional[str] = None) -> Optional[ChatModalResponse]:
    storage = create_buffer_storage(config)
    return await storage.flush(user_id, blob_type, buffer_ids, select_status, profile_config, project_id)


async def wait_insert_done_then_flush(user_id: str, blob_type: BlobType, config: Config, profile_config=None, project_id: Optional[str] = None) -> Optional[ChatModalResponse]:
    storage = create_buffer_storage(config)
    buffer_ids = await storage.get_ids_by_status(user_id, blob_type, BufferStatus.idle, project_id)
    if not buffer_ids:
        return None

    return await storage.flush(user_id, blob_type, buffer_ids, BufferStatus.idle, profile_config, project_id)


async def flush_buffer(user_id: str, blob_type: BlobType, config: Config, profile_config=None, project_id: Optional[str] = None) -> Optional[ChatModalResponse]:
    """Flush buffer with parallel status queries for improved performance."""
    storage = create_buffer_storage(config)

    # Parallel execution of status queries - optimized from serial execution
    idle_result, failed_result = await asyncio.gather(
        storage.get_ids_by_status(user_id, blob_type, BufferStatus.idle, project_id),
        storage.get_ids_by_status(user_id, blob_type, BufferStatus.failed, project_id),
        return_exceptions=True
    )

    buffer_ids: set[str] = set()

    if isinstance(idle_result, Exception):
        raise BufferStorageError(f"Failed to get idle buffer ids: {str(idle_result)}") from idle_result
    buffer_ids.update(idle_result)

    if isinstance(failed_result, Exception):
        raise BufferStorageError(f"Failed to get failed buffer ids: {str(failed_result)}") from failed_result
    buffer_ids.update(failed_result)

    if not buffer_ids:
        return None

    return await storage.flush(user_id, blob_type, list(buffer_ids), BufferStatus.idle, profile_config, project_id)
