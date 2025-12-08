"""
Storage Manager - Unified storage initialization and lifecycle management.

This module provides a centralized StorageManager that coordinates initialization
and access to all storage backends (table, search, buffer) with consistent patterns.
"""

import threading
from typing import Optional, Dict, Tuple
from ...config import Config, TRACE_LOG


class StorageManager:
    """
    Central registry for all storage instances with unified lifecycle management.
    
    This class implements the singleton pattern for storage clients, ensuring
    consistent initialization and access patterns across the application.
    """
    
    # Class-level storage caches
    _table_storage_cache: Dict[Tuple, 'LindormTableStorage'] = {}
    _search_storage_cache: Dict[Tuple, 'LindormSearchStorage'] = {}
    _buffer_storage_cache: Dict[Tuple, 'LindormBufferStorage'] = {}
    
    # Thread-safe locks
    _table_lock = threading.Lock()
    _search_lock = threading.Lock()
    _buffer_lock = threading.Lock()
    
    # Initialization state
    _initialized = False
    _init_lock = threading.Lock()
    
    @classmethod
    def initialize(cls, config: Config) -> None:
        """
        Initialize all storage clients and create necessary tables/indexes.
        
        This method should be called once at application startup to ensure
        all storage backends are properly initialized.
        
        Args:
            config: Configuration object containing connection parameters
            
        Raises:
            Exception: If initialization fails
        """
        with cls._init_lock:
            if cls._initialized:
                TRACE_LOG.warning("system", "StorageManager already initialized, skipping re-initialization")
                return
                
            try:
                # Initialize table storage
                table_storage = cls.get_table_storage(config)
                table_storage.initialize_tables()
                
                # Initialize search storage
                search_storage = cls.get_search_storage(config)
                search_storage.initialize_indices()
                
                # Initialize buffer storage
                buffer_storage = cls.get_buffer_storage(config)
                buffer_storage.initialize_tables()
                
                cls._initialized = True
                TRACE_LOG.info("system", "StorageManager initialized successfully")
                
            except Exception as e:
                TRACE_LOG.error("system", f"StorageManager initialization failed: {str(e)}")
                # Clear any partially initialized instances
                cls.cleanup()
                raise
    
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
        Get or create a LindormSearchStorage instance.
        
        Args:
            config: Configuration object
            
        Returns:
            LindormSearchStorage instance
        """
        from .events import LindormSearchStorage
        
        cache_key = (
            config.lindorm_search_host,
            config.lindorm_search_port,
            config.lindorm_search_username
        )
        
        with cls._search_lock:
            if cache_key not in cls._search_storage_cache:
                cls._search_storage_cache[cache_key] = LindormSearchStorage(config)
            return cls._search_storage_cache[cache_key]
    
    @classmethod
    def get_buffer_storage(cls, config: Config):
        """
        Get or create a LindormBufferStorage instance.
        
        Args:
            config: Configuration object
            
        Returns:
            LindormBufferStorage instance
        """
        from .buffers import LindormBufferStorage
        
        host = config.lindorm_buffer_host or config.lindorm_table_host
        port = config.lindorm_buffer_port or config.lindorm_table_port
        username = config.lindorm_buffer_username or config.lindorm_table_username
        database = config.lindorm_buffer_database or config.lindorm_table_database
        
        cache_key = (host, port, username, database)
        
        with cls._buffer_lock:
            if cache_key not in cls._buffer_storage_cache:
                cls._buffer_storage_cache[cache_key] = LindormBufferStorage(config)
            return cls._buffer_storage_cache[cache_key]
    
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
                    TRACE_LOG.warning("system", f"Error closing table storage: {str(e)}")
            cls._table_storage_cache.clear()
        
        with cls._search_lock:
            for storage in cls._search_storage_cache.values():
                try:
                    if hasattr(storage, 'client') and storage.client:
                        storage.client.close()
                except Exception as e:
                    TRACE_LOG.warning("system", f"Error closing search storage: {str(e)}")
            cls._search_storage_cache.clear()
        
        with cls._buffer_lock:
            for storage in cls._buffer_storage_cache.values():
                try:
                    if hasattr(storage, '_pool') and storage._pool:
                        pass
                except Exception as e:
                    TRACE_LOG.warning("system", f"Error closing buffer storage: {str(e)}")
            cls._buffer_storage_cache.clear()
        
        with cls._init_lock:
            cls._initialized = False
        
        TRACE_LOG.info("system", "StorageManager cleanup completed")
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if StorageManager has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        with cls._init_lock:
            return cls._initialized


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
