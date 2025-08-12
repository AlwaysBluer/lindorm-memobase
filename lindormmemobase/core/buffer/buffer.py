import json
import uuid
import asyncio
from datetime import datetime
from typing import Callable, Awaitable, List, Dict, Any, Optional
from mysql.connector import pooling

from ...config import TRACE_LOG, Config
from ..constants import BufferStatus
from ...models.blob import BlobType, Blob
from ...models.promise import Promise, CODE
from ...models.response import ChatModalResponse
from ...models.profile_topic import ProfileConfig

from ...utils.tools import get_blob_token_size
from ...core.extraction.processor.process_blobs import process_blobs

# lindorm 宽表SQL不支持JOIN
BlobProcessFunc = Callable[
    [str, Optional[ProfileConfig], list[Blob], Config],  # user_id, profile_config, blobs, config
    Awaitable[Promise[ChatModalResponse]],
]

BLOBS_PROCESS: dict[BlobType, BlobProcessFunc] = {BlobType.chat: process_blobs}

lindorm_buffer_storage = None


def get_lindorm_buffer_storage(config):
    global lindorm_buffer_storage
    if lindorm_buffer_storage is None and config is None:
        raise Exception("require configuration to connect to lindorm")
    elif lindorm_buffer_storage is None:
        lindorm_buffer_storage = LindormBufferStorage(config)
    return lindorm_buffer_storage


class LindormBufferStorage:
    def __init__(self, config):
        self.config = config
        self.pool = None

    def _get_pool(self):
        if self.pool is None:
            try:
                self.pool = pooling.MySQLConnectionPool(
                    pool_name="buffer_pool",
                    pool_size=10,
                    pool_reset_session=True,
                    host=self.config.lindorm_table_host,
                    port=self.config.lindorm_table_port,
                    user=self.config.lindorm_table_username,
                    password=self.config.lindorm_table_password,
                    database=self.config.lindorm_table_database,
                    autocommit=False
                )
            except Exception as e:
                raise Exception(f"Failed to create database connection pool: {str(e)}")
        return self.pool

    def _ensure_tables(self):
        pool = self._get_pool()
        conn = pool.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            # Buffer Zone 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS buffer_zone (
                    user_id VARCHAR(255) NOT NULL,
                    blob_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    status VARCHAR(50) NOT NULL,
                    blob_type VARCHAR(50) NOT NULL,
                    token_size INT,
                    PRIMARY KEY(user_id, blob_id)
                )
            """)
            # Blob Content 表 - 存储具体内容
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blob_content (
                    user_id VARCHAR(255) NOT NULL,
                    blob_id VARCHAR(255) NOT NULL,
                    blob_data VARCHAR(65535) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(user_id, blob_id)
                )
            """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            if cursor:
                cursor.close()
            conn.close()

    async def insert_blob_to_buffer(self, user_id: str, blob_id: str, blob_data: Blob) -> Promise[None]:
        """插入blob到buffer zone和blob content表"""

        def _insert_sync():
            self._ensure_tables()
            pool = self._get_pool()
            conn = pool.get_connection()
            cursor = None

            try:
                cursor = conn.cursor()
                now = datetime.utcnow()

                # 插入到buffer_zone表
                cursor.execute(
                    """
                    INSERT INTO buffer_zone (user_id, blob_id, created_at, updated_at, status, blob_type, token_size)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (str(user_id), str(blob_id), now, now, BufferStatus.idle, str(blob_data.type),
                     get_blob_token_size(blob_data))
                )

                # 插入到blob_content表
                cursor.execute(
                    """
                    INSERT INTO blob_content (user_id, blob_id, blob_data, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(user_id), str(blob_id), json.dumps(blob_data.model_dump(), default=str), now, now)
                )
                conn.commit()
                return blob_id
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _insert_sync)
            return Promise.resolve(None)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to insert blob to buffer: {str(e)}")

    async def get_buffer_capacity(self, user_id: str, blob_type: BlobType) -> Promise[int]:
        """获取buffer容量"""

        def _get_capacity_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            cursor = None

            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM buffer_zone 
                    WHERE user_id = %s AND blob_type = %s AND status = %s
                    """,
                    (str(user_id), str(blob_type), BufferStatus.idle)
                )
                result = cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                raise e
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        try:
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(None, _get_capacity_sync)
            return Promise.resolve(count)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get buffer capacity: {str(e)}")

    async def detect_buffer_full_or_not(self, user_id: str, blob_type: BlobType, global_config: Config) -> Promise[
        List[str]]:
        """检测buffer是否已满，如果已满，则返回blob_ids列表"""

        def _detect_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            cursor = None

            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT blob_id, token_size FROM buffer_zone 
                    WHERE user_id = %s AND blob_type = %s AND status = %s
                    """,
                    (str(user_id), str(blob_type), BufferStatus.idle)
                )
                results = cursor.fetchall()

                if not results:
                    return []

                blob_ids = [row[0] for row in results]
                total_token_size = sum(row[1] for row in results if row[1])

                if total_token_size > global_config.max_chat_blob_buffer_token_size:
                    TRACE_LOG.info(
                        user_id,
                        f"Flush {blob_type} buffer due to reach maximum token size({total_token_size} > {global_config.max_chat_blob_buffer_token_size})"
                    )
                    return blob_ids

                return []
            except Exception as e:
                raise e
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        try:
            loop = asyncio.get_event_loop()
            buffer_ids = await loop.run_in_executor(None, _detect_sync)
            return Promise.resolve(buffer_ids)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get unprocessed buffer ids: {str(e)}")

    async def get_unprocessed_blob_ids(self, user_id: str, blob_type: BlobType,
                                       select_status: str = BufferStatus.idle) -> Promise[List[str]]:
        """获取未处理的blob ids"""

        def _get_ids_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            cursor = None

            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT blob_id FROM buffer_zone 
                    WHERE user_id = %s AND blob_type = %s AND status = %s
                    """,
                    (str(user_id), str(blob_type), select_status)
                )
                results = cursor.fetchall()
                return [row[0] for row in results]
            except Exception as e:
                raise e
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        try:
            loop = asyncio.get_event_loop()
            buffer_ids = await loop.run_in_executor(None, _get_ids_sync)
            return Promise.resolve(buffer_ids)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to get unprocessed buffer ids: {str(e)}")

    async def flush_buffer_by_ids(
            self,
            user_id: str,
            blob_type: BlobType,
            blob_ids: list[str],
            select_status: str = BufferStatus.idle,
            profile_config=None,
    ) -> Promise[ChatModalResponse | None]:
        """刷新指定的buffer ids"""
        if blob_type not in BLOBS_PROCESS:
            return Promise.reject(CODE.BAD_REQUEST, f"Blob type {blob_type} not supported")
        if not len(blob_ids):
            return Promise.resolve(None)

        def _flush_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            cursor = None

            try:
                cursor = conn.cursor()

                # 1. 查询buffer数据（不使用JOIN，因为Lindorm不支持）
                buffer_ids_placeholder = ','.join(['%s'] * len(blob_ids))

                # 先查询buffer_zone表
                query_buffer = f"""
                    SELECT 
                        blob_id,
                        token_size,
                        created_at
                    FROM buffer_zone
                    WHERE user_id = %s 
                        AND blob_type = %s 
                        AND status = %s 
                        AND blob_id IN ({buffer_ids_placeholder})
                    ORDER BY created_at
                """
                cursor.execute(query_buffer, [str(user_id), str(blob_type), select_status] + blob_ids)
                buffer_data = cursor.fetchall()

                if not buffer_data:
                    TRACE_LOG.info(
                        user_id,
                        f"No {blob_type} buffer to flush",
                    )
                    return None

                # 获取所有blob_ids from buffer_data
                retrieved_blob_ids = [row[0] for row in buffer_data]
                retrieved_blob_ids_placeholder = ','.join(['%s'] * len(retrieved_blob_ids))

                # 再查询blob_content表
                query_blob = f"""
                    SELECT 
                        blob_id,
                        blob_data,
                        created_at
                    FROM blob_content
                    WHERE user_id = %s 
                        AND blob_id IN ({retrieved_blob_ids_placeholder})
                """
                cursor.execute(query_blob, [str(user_id)] + retrieved_blob_ids)
                blob_content_data = cursor.fetchall()

                # 创建blob_id到blob_data的映射
                blob_map = {row[0]: (row[1], row[2]) for row in blob_content_data}

                # 合并buffer和blob数据
                buffer_blob_data = []
                for buffer_row in buffer_data:
                    blob_id, token_size, buffer_created_at = buffer_row
                    if blob_id in blob_map:
                        blob_data, created_at = blob_map[blob_id]
                        buffer_blob_data.append((blob_id, token_size, buffer_created_at, blob_data, created_at))

                if not buffer_blob_data:
                    TRACE_LOG.info(
                        user_id,
                        f"No {blob_type} buffer to flush",
                    )
                    return None

                # 获取实际需要处理的blob_ids
                process_blob_ids = [row[0] for row in buffer_blob_data]

                # 2. 更新buffer状态为processing
                if select_status != BufferStatus.processing:
                    for blob_id in process_blob_ids:
                        cursor.execute(
                            "UPDATE buffer_zone SET status = %s WHERE user_id = %s AND blob_id = %s",
                            (BufferStatus.processing, str(user_id), blob_id)
                        )

                # 构建blobs数据
                blobs = []
                total_token_size = 0
                for row in buffer_blob_data:
                    blob_id, token_size, buffer_created_at, blob_data_json, created_at = row
                    total_token_size += token_size if token_size else 0

                    # 解析blob_data
                    blob_data = json.loads(blob_data_json)

                    # 确保使用数据库中的 created_at
                    blob_data['created_at'] = created_at

                    # 根据blob_type创建相应的Blob对象
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
                        # 其他类型暂时不支持
                        raise Exception(f"Unsupported blob type: {blob_type}")

                    blobs.append(blob)

                TRACE_LOG.info(
                    user_id,
                    f"Flush {blob_type} buffer with {len(buffer_blob_data)} blobs and total token size({total_token_size})",
                )

                conn.commit()

                return {
                    'blobs': blobs,
                    'process_blob_ids': process_blob_ids,
                    'blob_ids': [row[0] for row in buffer_blob_data]
                }

            except Exception as e:
                conn.rollback()
                raise e
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        try:
            loop = asyncio.get_event_loop()
            flush_data = await loop.run_in_executor(None, _flush_sync)

            if flush_data is None:
                return Promise.resolve(None)

            # 3. 处理blobs 
            p = await BLOBS_PROCESS[blob_type](user_id, profile_config, flush_data['blobs'], self.config)

            # 4. 更新状态基于处理结果
            def _update_status_sync(success: bool):
                pool = self._get_pool()
                conn = pool.get_connection()
                cursor = None

                try:
                    cursor = conn.cursor()

                    if success:
                        # 更新buffer状态为done
                        process_blob_ids = flush_data['process_blob_ids']
                        for blob_id in process_blob_ids:
                            cursor.execute(
                                "UPDATE buffer_zone SET status = %s WHERE user_id = %s AND blob_id = %s",
                                (BufferStatus.done, str(user_id), blob_id)
                            )

                        TRACE_LOG.info(
                            user_id,
                            f"Flushed {blob_type} buffer(size: {len(flush_data['blobs'])})",
                        )
                    else:
                        # 更新buffer状态为failed
                        process_blob_ids = flush_data['process_blob_ids']
                        for blob_id in process_blob_ids:
                            cursor.execute(
                                "UPDATE buffer_zone SET status = %s WHERE user_id = %s AND blob_id = %s",
                                (BufferStatus.failed, str(user_id), blob_id)
                            )

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    TRACE_LOG.error(
                        user_id,
                        f"DB Error while updating buffer status: {e}",
                    )
                    raise e
                finally:
                    if cursor:
                        cursor.close()
                    conn.close()

            if not p.ok():
                await loop.run_in_executor(None, lambda: _update_status_sync(False))
                return p
            else:
                await loop.run_in_executor(None, lambda: _update_status_sync(True))
                return p

        except Exception as e:
            TRACE_LOG.error(
                user_id,
                f"Error in flush_buffer: {e}",
            )
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to flush buffer: {str(e)}")

    async def flush_buffer(
            self,
            user_id: str,
            blob_type: BlobType
    ) -> Promise[ChatModalResponse | None]:
        """刷新buffer中所有未处理的数据"""
        p = await self.get_unprocessed_blob_ids(user_id, blob_type)
        if not p.ok():
            return p

        buffer_ids = p.data()
        if not buffer_ids:
            return Promise.resolve(None)

        p = await self.flush_buffer_by_ids(user_id, blob_type, buffer_ids, BufferStatus.idle, None)
        return p


# 对外接口函数
async def get_buffer_capacity(
        user_id: str,
        blob_type: BlobType,
        config: Config
) -> Promise[int]:
    storage = get_lindorm_buffer_storage(config)
    return await storage.get_buffer_capacity(user_id, blob_type)


async def insert_blob_to_buffer(
        user_id: str,
        blob_id: str,
        blob_data: Blob,
        config: Config,
) -> Promise[None]:
    storage = get_lindorm_buffer_storage(config)
    return await storage.insert_blob_to_buffer(user_id, blob_id, blob_data)


async def detect_buffer_full_or_not(
        user_id: str,
        blob_type: BlobType,
        config: Config,
) -> Promise[List[str]]:
    storage = get_lindorm_buffer_storage(config)
    return await storage.detect_buffer_full_or_not(user_id, blob_type, config)


async def get_unprocessed_buffer_ids(
        user_id: str,
        blob_type: BlobType,
        config: Config,
        select_status: str = BufferStatus.idle,
) -> Promise[List[str]]:
    storage = get_lindorm_buffer_storage(config)
    return await storage.get_unprocessed_blob_ids(user_id, blob_type, select_status)


async def flush_buffer_by_ids(
        user_id: str,
        blob_type: BlobType,
        buffer_ids: list[str],
        config: Config,
        select_status: str = BufferStatus.idle,
        profile_config=None,
) -> Promise[List[str]]:
    storage = get_lindorm_buffer_storage(config)
    return await storage.flush_buffer_by_ids(user_id, blob_type, buffer_ids, select_status, profile_config)


# 数据积累和触发机制
async def wait_insert_done_then_flush(
        user_id: str,
        blob_type: BlobType,
        config: Config,
        profile_config=None
) -> Promise[ChatModalResponse | None]:
    """等待插入完成后刷新buffer"""
    p = await get_unprocessed_buffer_ids(user_id, blob_type, config)
    if not p.ok():
        return p

    buffer_ids = p.data()
    if not buffer_ids:
        return Promise.resolve(None)

    p = await flush_buffer_by_ids(user_id, blob_type, buffer_ids, config, BufferStatus.idle, profile_config)
    return p


async def flush_buffer(
        user_id: str,
        blob_type: BlobType,
        config: Config,
        profile_config=None
) -> Promise[ChatModalResponse | None]:
    """刷新buffer中所有未处理的数据"""
    p = await get_unprocessed_buffer_ids(user_id, blob_type, config)
    if not p.ok():
        return p

    buffer_ids = p.data()
    if not buffer_ids:
        return Promise.resolve(None)

    p = await flush_buffer_by_ids(user_id, blob_type, buffer_ids, config, BufferStatus.idle, profile_config)
    return p
