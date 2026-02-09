"""
Storage Manager - Unified storage initialization and lifecycle management.

This module provides a centralized StorageManager that coordinates initialization
and access to all storage backends (table, search, buffer) with consistent patterns.
"""

import threading
import time
import asyncio
from typing import Optional, Dict, Tuple
from lindormmemobase.config import Config, LOG
from .event_gists import LindormEventGistsStorage
from .buffers import LindormBufferStorage


class StorageManager:
    """
    Central registry for all storage instances with unified lifecycle management.
    
    This class implements the singleton pattern for storage clients, ensuring
    consistent initialization and access patterns across the application.
    """
    
    # Class-level storage caches
    _table_storage_cache: Dict[Tuple, 'LindormTableStorage'] = {}
    _search_storage_cache: Dict[Tuple, 'LindormEventsStorage'] = {}
    _event_gists_storage_cache: Dict[Tuple, 'LindormEventGistsStorage'] = {}
    _buffer_storage_cache: Dict[Tuple, 'LindormBufferStorage'] = {}
    _image_storage_cache: Dict[Tuple, 'LindormImageStorage'] = {}
    _topic_config_storage_cache: Dict[Tuple, 'TopicConfigStorage'] = {}
    _pending_profiles_storage_cache: Dict[Tuple, 'PendingProfiles'] = {}

    # Thread-safe locks
    _table_lock = threading.Lock()
    _search_lock = threading.Lock()
    _event_gists_lock = threading.Lock()
    _buffer_lock = threading.Lock()
    _image_lock = threading.Lock()
    _topic_config_lock = threading.Lock()
    _pending_profiles_lock = threading.Lock()
    
    # Initialization state
    _initialized = False
    _init_lock = threading.Lock()
    _init_task: Optional[asyncio.Task] = None
    _init_task_loop: Optional[asyncio.AbstractEventLoop] = None
    
    @classmethod
    async def initialize(cls, config: Config) -> None:
        """
        Initialize all storage clients and create necessary tables/indexes concurrently.

        This method should be called once at application startup to ensure
        all storage backends are properly initialized.

        Args:
            config: Configuration object containing connection parameters

        Raises:
            Exception: If initialization fails
        """
        if cls.is_initialized():
            LOG.warning("StorageManager already initialized, skipping re-initialization")
            return

        loop = asyncio.get_running_loop()
        with cls._init_lock:
            if cls._initialized:
                LOG.warning("StorageManager already initialized, skipping re-initialization")
                return
            if cls._init_task is None or cls._init_task_loop is not loop:
                cls._init_task = loop.create_task(cls._initialize_impl(config))
                cls._init_task_loop = loop
            init_task = cls._init_task

        await init_task

    @classmethod
    async def _initialize_impl(cls, config: Config) -> None:
        try:
            # Get all storage instances first
            table_storage = cls.get_table_storage(config)
            search_storage = cls.get_search_storage(config)
            event_gists_storage = cls.get_event_gists_storage(config)
            buffer_storage = cls.get_buffer_storage(config)
            image_storage = cls.get_image_storage(config)
            pending_profiles_storage = cls.get_pending_profiles_storage(config)

            # Run all initializations concurrently for faster startup
            loop = asyncio.get_running_loop()
            await asyncio.gather(
                loop.run_in_executor(None, table_storage.initialize_tables),
                loop.run_in_executor(None, search_storage.initialize_tables_and_indices),
                loop.run_in_executor(None, event_gists_storage.initialize_tables_and_indices),
                loop.run_in_executor(None, buffer_storage.initialize_tables),
                loop.run_in_executor(None, image_storage.initialize_tables_and_indices),
                loop.run_in_executor(None, pending_profiles_storage.initialize_tables),
            )

            with cls._init_lock:
                cls._initialized = True
            LOG.info("StorageManager initialized successfully")

        except Exception as e:
            LOG.error(f"StorageManager initialization failed: {str(e)}")
            # Clear any partially initialized instances
            cls.cleanup()
            raise
        finally:
            with cls._init_lock:
                if cls._init_task is not None and cls._init_task.done():
                    cls._init_task = None
                    cls._init_task_loop = None
    
    @classmethod
    def get_table_storage(cls, config: Config):
        """
        Get or create a LindormTableStorage instance.
        
        Returns cached instance if available for the same configuration,
        otherwise creates and caches a new instance.
        
        Args:
            config: Configuration object
            
        Returns:
            LindormTableStorage instance
        """
        from .user_profiles import LindormTableStorage
        cache_key = (
            config.lindorm_table_host,
            config.lindorm_table_port,
            config.lindorm_table_username,
            config.lindorm_table_database
        )
        
        with cls._table_lock:
            if cache_key not in cls._table_storage_cache:
                cls._table_storage_cache[cache_key] = LindormTableStorage(config)
            return cls._table_storage_cache[cache_key]
    
    @classmethod
    def get_search_storage(cls, config: Config):
        """
        Get or create a LindormEventsStorage instance.
        
        Args:
            config: Configuration object
            
        Returns:
            LindormEventsStorage instance
        """
        # Import here to avoid circular dependency
        from .events import LindormEventsStorage
        
        cache_key = (
            config.lindorm_search_host,
            config.lindorm_search_port,
            config.lindorm_search_username
        )
        
        with cls._search_lock:
            if cache_key not in cls._search_storage_cache:
                cls._search_storage_cache[cache_key] = LindormEventsStorage(config)
            return cls._search_storage_cache[cache_key]
    
    @classmethod
    def get_event_gists_storage(cls, config: Config):
        """
        Get or create a LindormEventGistsStorage instance.
        
        Args:
            config: Configuration object
            
        Returns:
            LindormEventGistsStorage instance
        """
        cache_key = (
            config.lindorm_search_host,
            config.lindorm_search_port,
            config.lindorm_search_username
        )
        
        with cls._event_gists_lock:
            if cache_key not in cls._event_gists_storage_cache:
                cls._event_gists_storage_cache[cache_key] = LindormEventGistsStorage(config)
            return cls._event_gists_storage_cache[cache_key]
    
    @classmethod
    def get_buffer_storage(cls, config: Config):
        """
        Get or create a LindormBufferStorage instance.

        Args:
            config: Configuration object

        Returns:
            LindormBufferStorage instance
        """
        cache_key = (
            config.lindorm_table_host,
            config.lindorm_table_port,
            config.lindorm_table_username,
            config.lindorm_table_database
        )

        with cls._buffer_lock:
            if cache_key not in cls._buffer_storage_cache:
                cls._buffer_storage_cache[cache_key] = LindormBufferStorage(config)
            return cls._buffer_storage_cache[cache_key]

    @classmethod
    def get_image_storage(cls, config: Config):
        """
        Get or create a LindormImageStorage instance.

        Args:
            config: Configuration object

        Returns:
            LindormImageStorage instance
        """
        from .images import LindormImageStorage

        cache_key = (
            config.lindorm_table_host,
            config.lindorm_table_port,
            config.lindorm_table_username,
            config.lindorm_table_database,
            config.lindorm_search_host,
            config.lindorm_search_port,
            config.lindorm_search_username,
        )

        with cls._image_lock:
            if cache_key not in cls._image_storage_cache:
                cls._image_storage_cache[cache_key] = LindormImageStorage(config)
            return cls._image_storage_cache[cache_key]

    @classmethod
    def get_topic_config_storage(cls, config: Config):
        """
        Get or create a TopicConfigStorage instance.

        Args:
            config: Configuration object

        Returns:
            TopicConfigStorage instance
        """
        from .topic_configs import TopicConfigStorage

        cache_key = (
            config.lindorm_table_host,
            config.lindorm_table_port,
            config.lindorm_table_username,
            config.lindorm_table_database
        )

        with cls._topic_config_lock:
            if cache_key not in cls._topic_config_storage_cache:
                cls._topic_config_storage_cache[cache_key] = TopicConfigStorage(config)
            return cls._topic_config_storage_cache[cache_key]

    @classmethod
    def get_pending_profiles_storage(cls, config: Config):
        """
        Get or create a PendingProfiles storage instance.

        Args:
            config: Configuration object

        Returns:
            PendingProfiles instance
        """
        from .pending_profiles import PendingProfiles

        cache_key = (
            config.lindorm_table_host,
            config.lindorm_table_port,
            config.lindorm_table_username,
            config.lindorm_table_database
        )

        with cls._pending_profiles_lock:
            if cache_key not in cls._pending_profiles_storage_cache:
                cls._pending_profiles_storage_cache[cache_key] = PendingProfiles(config)
            return cls._pending_profiles_storage_cache[cache_key]

    @classmethod
    def cleanup(cls) -> None:
        """
        Close all connections and clear storage caches.
        
        This method should be called during application shutdown to ensure
        proper cleanup of resources.
        """
        with cls._table_lock:
            for storage in cls._table_storage_cache.values():
                try:
                    if hasattr(storage, 'pool') and storage.pool:
                        # Connection pools don't have explicit close in mysql.connector.pooling
                        pass
                except Exception as e:
                    LOG.warning(f"Error closing table storage: {str(e)}")
            cls._table_storage_cache.clear()
        
        with cls._search_lock:
            for storage in cls._search_storage_cache.values():
                try:
                    if hasattr(storage, 'client') and storage.client:
                        storage.client.close()
                except Exception as e:
                    LOG.warning(f"Error closing search storage: {str(e)}")
            cls._search_storage_cache.clear()
        
        with cls._event_gists_lock:
            for storage in cls._event_gists_storage_cache.values():
                try:
                    if hasattr(storage, 'client') and storage.client:
                        storage.client.close()
                except Exception as e:
                    LOG.warning(f"Error closing event gists storage: {str(e)}")
            cls._event_gists_storage_cache.clear()
        
        with cls._buffer_lock:
            for storage in cls._buffer_storage_cache.values():
                try:
                    if hasattr(storage, '_pool') and storage._pool:
                        pass
                except Exception as e:
                    LOG.warning(f"Error closing buffer storage: {str(e)}")
            cls._buffer_storage_cache.clear()

        with cls._image_lock:
            for storage in cls._image_storage_cache.values():
                try:
                    if hasattr(storage, 'client') and storage.client:
                        storage.client.close()
                except Exception as e:
                    LOG.warning(f"Error closing image storage: {str(e)}")
            cls._image_storage_cache.clear()

        with cls._topic_config_lock:
            for storage in cls._topic_config_storage_cache.values():
                try:
                    if hasattr(storage, 'pool') and storage.pool:
                        pass
                except Exception as e:
                    LOG.warning(f"Error closing topic config storage: {str(e)}")
            cls._topic_config_storage_cache.clear()

        with cls._pending_profiles_lock:
            for storage in cls._pending_profiles_storage_cache.values():
                try:
                    if hasattr(storage, 'pool') and storage.pool:
                        pass
                except Exception as e:
                    LOG.warning(f"Error closing pending profiles storage: {str(e)}")
            cls._pending_profiles_storage_cache.clear()

        with cls._init_lock:
            cls._initialized = False
            cls._init_task = None
            cls._init_task_loop = None

        # Shutdown thread pool executor
        from .base import LindormStorageBase
        LindormStorageBase.shutdown_executor()

        LOG.info("StorageManager cleanup completed")
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if StorageManager has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        with cls._init_lock:
            return cls._initialized
    
    @classmethod
    async def reset_all_storage(
        cls,
        config: Config,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        """
        Reset all storage tables (buffer, events, user profiles).
        
        When user_id and project_id are both None, tables are dropped and recreated.
        Otherwise, data is deleted based on the provided filters.
        
        Args:
            config: Configuration object
            user_id: Optional user ID filter. If None, resets all users.
            project_id: Optional project ID filter. If None, resets all projects.
            
        Returns:
            Dictionary containing reset statistics:
            - buffer_deleted: Number of buffer rows deleted
            - events_deleted: Number of event rows deleted  
            - gists_deleted: Number of event gist rows deleted
            - profiles_deleted: Number of profile rows deleted
            - tables_recreated: Whether tables were dropped and recreated
        """
        result = {
            "buffer_deleted": 0,
            "events_deleted": 0,
            "gists_deleted": 0,
            "profiles_deleted": 0,
            "images_deleted": 0,
            "pending_profiles_deleted": 0,
            "tables_recreated": False
        }
        # Get storage instances
        buffer_storage = cls.get_buffer_storage(config)
        events_storage = cls.get_search_storage(config)
        event_gists_storage = cls.get_event_gists_storage(config)
        profiles_storage = cls.get_table_storage(config)
        image_storage = cls.get_image_storage(config)
        pending_profiles_storage = cls.get_pending_profiles_storage(config)

        # If both user_id and project_id are None, drop and recreate tables
        if user_id is None and project_id is None:
            # Drop and recreate buffer table
            await cls._drop_and_recreate_buffer_table(buffer_storage)
            # Drop and recreate events table
            await cls._drop_and_recreate_events_table(events_storage)
            # Drop and recreate event gists table
            await cls._drop_and_recreate_event_gists_table(event_gists_storage)
            # Drop and recreate profiles table
            await cls._drop_and_recreate_profiles_table(profiles_storage)
            # Drop and recreate images table
            await cls._drop_and_recreate_images_table(image_storage)
            # Drop and recreate pending profiles table
            await cls._drop_and_recreate_pending_profiles_table(pending_profiles_storage)
            result["tables_recreated"] = True
        elif user_id is None or user_id == "":
            raise ValueError("user_id cannot be None or empty")
        else:
            # Reset buffer
            buffer_count = await buffer_storage.reset(user_id, project_id)
            result["buffer_deleted"] = buffer_count
            # Reset events
            events_count = await events_storage.reset(user_id, project_id)
            result["events_deleted"] = events_count
            # Reset event gists
            gists_count = await event_gists_storage.reset(user_id, project_id)
            result["gists_deleted"] = gists_count
            # Reset profiles
            profiles_count = await profiles_storage.reset(user_id, project_id)
            result["profiles_deleted"] = profiles_count
            # Reset images
            images_count = await image_storage.reset(project_id, user_id)
            result["images_deleted"] = images_count
            # Reset pending profiles
            pending_count = await pending_profiles_storage.reset(user_id, project_id)
            result["pending_profiles_deleted"] = pending_count

        return result
    
    @classmethod
    async def _drop_and_recreate_buffer_table(cls, storage) -> None:
        """Drop and recreate BufferStorage table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS BufferStorage")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)
    
    @classmethod
    async def _drop_and_recreate_events_table(cls, storage) -> None:
        """Drop and recreate UserEvents table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP INDEX IF EXISTS srh_idx on UserEvents")
                cursor.execute("DROP TABLE IF EXISTS UserEvents")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables_and_indices()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)
    
    @classmethod
    async def _drop_and_recreate_event_gists_table(cls, storage) -> None:
        """Drop and recreate UserEventsGists table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP INDEX IF EXISTS srh_idx on UserEventsGists")
                cursor.execute("DROP TABLE IF EXISTS UserEventsGists")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables_and_indices()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)
    
    @classmethod
    async def _drop_and_recreate_profiles_table(cls, storage) -> None:
        """Drop and recreate UserProfiles table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP INDEX IF EXISTS srh_idx on UserProfiles")
                cursor.execute("DROP TABLE IF EXISTS UserProfiles")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables_and_indices()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)

    @classmethod
    async def _drop_and_recreate_images_table(cls, storage) -> None:
        """Drop and recreate ImageStore table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP INDEX IF EXISTS srh_idx on ImageStore")
                cursor.execute("DROP TABLE IF EXISTS ImageStore")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables_and_indices()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)

    @classmethod
    async def _drop_and_recreate_pending_profiles_table(cls, storage) -> None:
        """Drop and recreate PendingProfiles table."""
        def _drop_and_recreate_sync():
            pool = storage._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS PendingProfiles")
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            storage.initialize_tables()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _drop_and_recreate_sync)


# Backward compatibility functions
def get_lindorm_table_storage(config: Config):
    """Legacy function - delegates to StorageManager."""
    return StorageManager.get_table_storage(config)


def get_lindorm_search_storage(config: Config):
    """Legacy function - delegates to StorageManager."""
    return StorageManager.get_search_storage(config)


def create_buffer_storage(config: Config):
    """Legacy function - delegates to StorageManager."""
    return StorageManager.get_buffer_storage(config)


def get_lindorm_image_storage(config: Config):
    """Legacy function - delegates to StorageManager."""
    return StorageManager.get_image_storage(config)
