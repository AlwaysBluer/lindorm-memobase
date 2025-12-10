"""Base class for all Lindorm storage implementations.

This module provides common functionality for storage classes including:
- MySQL connection pool management
- Lindorm system settings configuration
- Reset/cleanup operations
- Configuration access
"""
import asyncio
from mysql.connector import pooling
from lindormmemobase.config import Config, LOG


class LindormStorageBase:
    """Base class for all Lindorm storage implementations.
    
    Provides common functionality:
    - MySQL connection pool management
    - Lindorm system settings configuration
    - Common utility methods
    
    Subclasses should override:
    - _get_pool_config(): Return pool configuration dict
    - _get_pool_name(): Return unique pool name
    - initialize_tables() or initialize_tables_and_indices(): Create tables/indices
    """
    
    def __init__(self, config: Config):
        """Initialize storage base.
        
        Args:
            config: Configuration object containing connection parameters
        """
        self.config = config
        self.pool = None
    
    def _get_pool_name(self) -> str:
        """Get pool name for this storage instance.
        
        Must be overridden by subclasses to provide unique pool names.
        
        Returns:
            Unique pool name string
        """
        raise NotImplementedError("Subclasses must implement _get_pool_name()")
    
    def _get_pool_config(self) -> dict:
        """Get connection pool configuration.
        
        Must be overridden by subclasses to provide specific pool settings.
        
        Returns:
            Dictionary with pool configuration (host, port, user, password, database, pool_size)
        """
        raise NotImplementedError("Subclasses must implement _get_pool_config()")
    
    def _get_pool(self) -> pooling.MySQLConnectionPool:
        """Get or create MySQL connection pool.
        
        Creates a new pool on first access, caches it for subsequent calls.
        Subclasses can override _get_pool_config() to customize pool settings.
        
        Returns:
            MySQLConnectionPool instance
        """
        if self.pool is None:
            pool_config = self._get_pool_config()
            self.pool = pooling.MySQLConnectionPool(
                pool_name=self._get_pool_name(),
                pool_size=pool_config.get('pool_size', 32),
                pool_reset_session=True,
                host=pool_config['host'],
                port=pool_config['port'],
                user=pool_config['user'],
                password=pool_config['password'],
                database=pool_config['database'],
                autocommit=False
            )
        return self.pool
    
    def _configure_lindorm_settings(self):
        """Configure Lindorm system settings for wide table operations.
        
        This method sets necessary Lindorm-specific configurations that are required
        for proper operation of wide table storage.
        
        Current settings:
        - lindorm.allow.range.delete: Enables DELETE operations with partial primary keys
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            
            # Enable range delete to allow DELETE operations with partial primary keys
            # Required for deleting by user_id or project_id without specifying all PK columns
            try:
                cursor.execute("ALTER SYSTEM SET `lindorm.allow.range.delete`=TRUE")
                LOG.info(f"{self.__class__.__name__}: Lindorm setting configured: lindorm.allow.range.delete=TRUE")
            except Exception as e:
                # Setting might already be enabled or not supported in this Lindorm version
                LOG.warning(f"{self.__class__.__name__}: Failed to set lindorm.allow.range.delete: {str(e)}")
            
            # Add other Lindorm-specific settings here as needed
            # Subclasses can override this method to add their own settings
            
            conn.commit()
        except Exception as e:
            LOG.warning("Lindorm settings configuration encountered errors: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    
    async def _execute_sync_operation(self, sync_func, error_message: str = "Operation failed"):
        """Execute a synchronous database operation asynchronously.
        
        Helper method to run sync database operations in executor.
        This is the recommended pattern for all async database operations.
        
        Example usage:
            def _my_sync_operation():
                pool = self._get_pool()
                conn = pool.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT ...")
                    result = cursor.fetchall()
                    conn.commit()
                    return result
                finally:
                    cursor.close()
                    conn.close()
            
            result = await self._execute_sync_operation(
                _my_sync_operation,
                "Failed to fetch data"
            )
        
        Args:
            sync_func: Synchronous function to execute
            error_message: Error message prefix for exceptions
            
        Returns:
            Result from sync_func
            
        Raises:
            Exception with error_message prefix
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, sync_func)
            return result
        except Exception as e:
            raise Exception(f"{error_message}: {str(e)}") from e
    
    def get_config(self) -> Config:
        """Get configuration object.
        
        Returns:
            Config object used to initialize this storage
        """
        return self.config