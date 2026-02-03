"""TopicConfigStorage - Project-specific ProfileConfig storage with caching.

This module provides storage for project-specific profile configurations,
backed by Lindorm wide table with in-memory caching support.
"""
import threading
import time
from dataclasses import dataclass
from typing import Optional

from lindormmemobase.config import Config, LOG
from lindormmemobase.models.profile_topic import ProfileConfig

TABLE_NAME = "ProjectProfileConfigs"
DEFAULT_CACHE_TTL = 300  # 5 minutes


@dataclass
class CacheEntry:
    """Cache entry with value and expiration time."""
    value: Optional[ProfileConfig]  # None means "no config in DB" (negative cache)
    expires_at: float


class TopicConfigStorage:
    """
    Storage layer for project-specific ProfileConfig.

    Features:
    - Lindorm wide table backed storage
    - In-memory caching with TTL and negative caching
    - Manual cache invalidation support
    """

    def __init__(self, config: Config, cache_ttl: int = DEFAULT_CACHE_TTL):
        """Initialize TopicConfigStorage.

        Args:
            config: Configuration object containing connection parameters
            cache_ttl: Cache time-to-live in seconds (default: 300)
        """
        self.config = config
        self._cache_ttl = cache_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._pool = None

        # Create table if not exists
        self._ensure_table_exists()

    def _get_pool(self):
        """Get or create MySQL connection pool."""
        if self._pool is None:
            from mysql.connector import pooling

            pooling.CNX_POOL_MAXSIZE = 2999
            self._pool = pooling.MySQLConnectionPool(
                pool_name="topic_config_pool",
                pool_size=10,
                pool_reset_session=True,
                host=self.config.lindorm_table_host,
                port=self.config.lindorm_table_port,
                user=self.config.lindorm_table_username,
                password=self.config.lindorm_table_password,
                database=self.config.lindorm_table_database,
                autocommit=False,
                use_pure=True
            )
        return self._pool

    def _ensure_table_exists(self):
        """Create table if not exists using SHOW TABLES for fast check."""
        try:
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(f"SHOW TABLES LIKE '{TABLE_NAME}'")
                if cursor.fetchone():
                    LOG.info(f"Table {TABLE_NAME} already exists")
                    return

                # Table doesn't exist, create it
                create_sql = f"""
                CREATE TABLE {TABLE_NAME} (
                    project_id VARCHAR(255) NOT NULL,
                    config_yaml VARCHAR(65535) NOT NULL COMMENT 'Complete ProfileConfig YAML content',
                    updated_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP,
                    PRIMARY KEY(project_id)
                )
                """
                cursor.execute(create_sql)
                conn.commit()
                LOG.info(f"Table {TABLE_NAME} created successfully")
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            LOG.error(f"Failed to ensure table exists: {e}")
            # Don't raise - allow system to function with YAML fallback

    async def get_profile_config(self, project_id: str) -> Optional[ProfileConfig]:
        """
        Get ProfileConfig for a specific project.

        Args:
            project_id: Project identifier

        Returns:
            ProfileConfig object if found in DB, None if not found (caller should fallback)
        """
        # 1. Check cache
        cached_entry = self._get_from_cache(project_id)
        if cached_entry is not None:
            LOG.debug(f"Cache {'hit' if cached_entry.value else 'miss (negative)'} for project {project_id}")
            return cached_entry.value

        # 2. Query DB
        try:
            config = await self._load_from_db(project_id)
            self._update_cache(project_id, config)
            if config:
                LOG.info(f"Loaded config from DB for project {project_id}")
            else:
                LOG.info(f"No config found in DB for project {project_id}")
            return config
        except Exception as e:
            LOG.error(f"Failed to load config from DB for project {project_id}: {e}")
            raise

    def _get_from_cache(self, project_id: str) -> Optional[CacheEntry]:
        """Get from cache if not expired."""
        with self._cache_lock:
            entry = self._cache.get(project_id)
            if entry and time.time() < entry.expires_at:
                return entry
            # Cache expired or not found
            self._cache.pop(project_id, None)
            return None

    def _update_cache(self, project_id: str, config: Optional[ProfileConfig]) -> None:
        """Update cache with new value (None for negative cache)."""
        with self._cache_lock:
            expires_at = time.time() + self._cache_ttl
            self._cache[project_id] = CacheEntry(value=config, expires_at=expires_at)
            LOG.debug(f"Cache updated for project {project_id}, value={'present' if config else 'None (negative)'}")

    def invalidate_cache(self, project_id: Optional[str] = None) -> None:
        """
        Invalidate cache for specific project or all projects.

        Args:
            project_id: Specific project ID to invalidate. If None, invalidates all.
        """
        with self._cache_lock:
            if project_id:
                self._cache.pop(project_id, None)
                LOG.info(f"Cache invalidated for project {project_id}")
            else:
                self._cache.clear()
                LOG.info("All cache invalidated")

    async def _load_from_db(self, project_id: str) -> Optional[ProfileConfig]:
        """Load config from Lindorm database."""
        import asyncio

        def _load_sync():
            try:
                pool = self._get_pool()
                conn = pool.get_connection()
                try:
                    cursor = conn.cursor()

                    query = f"""
                    SELECT config_yaml
                    FROM {TABLE_NAME}
                    WHERE project_id = %s
                    LIMIT 1
                    """
                    cursor.execute(query, (project_id,))
                    row = cursor.fetchone()

                    if not row or not row[0]:
                        return None

                    config_yaml = row[0]
                    return ProfileConfig.load_config_string(config_yaml)
                finally:
                    cursor.close()
                    conn.close()
            except Exception as e:
                LOG.error(f"Database query failed for project {project_id}: {e}")
                raise

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _load_sync)
        except Exception as e:
            LOG.error(f"Failed to load config from DB for project {project_id}: {e}")
            raise

    async def set_profile_config(self, project_id: str, config: ProfileConfig) -> None:
        """
        Set or update ProfileConfig for a specific project in the database.

        Args:
            project_id: Project identifier
            config: ProfileConfig object to store

        Raises:
            Exception: If database operation fails
        """
        import asyncio
        from datetime import datetime

        def _set_sync():
            try:
                pool = self._get_pool()
                conn = pool.get_connection()
                try:
                    cursor = conn.cursor()

                    # Convert ProfileConfig to YAML string
                    config_yaml = config._to_yaml_string()

                    # Use INSERT ... ON DUPLICATE KEY UPDATE for MySQL/Lindorm
                    upsert_sql = f"""
                    INSERT INTO {TABLE_NAME} (project_id, config_yaml, updated_at, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        config_yaml = VALUES(config_yaml),
                        updated_at = VALUES(updated_at)
                    """
                    now = datetime.now()
                    cursor.execute(upsert_sql, (project_id, config_yaml, now, now))
                    conn.commit()

                    LOG.info(f"Config saved to DB for project {project_id}")
                finally:
                    cursor.close()
                    conn.close()
            except Exception as e:
                LOG.error(f"Failed to save config to DB for project {project_id}: {e}")
                raise

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _set_sync)
            # Invalidate cache after update
            self.invalidate_cache(project_id)
        except Exception as e:
            LOG.error(f"Failed to set config for project {project_id}: {e}")
            raise

    async def delete_profile_config(self, project_id: str) -> bool:
        """
        Delete ProfileConfig for a specific project from the database.

        Args:
            project_id: Project identifier

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If database operation fails
        """
        import asyncio

        def _delete_sync():
            try:
                pool = self._get_pool()
                conn = pool.get_connection()
                try:
                    cursor = conn.cursor()

                    delete_sql = f"""
                    DELETE FROM {TABLE_NAME}
                    WHERE project_id = %s
                    """
                    cursor.execute(delete_sql, (project_id,))
                    conn.commit()

                    deleted = cursor.rowcount > 0
                    if deleted:
                        LOG.info(f"Config deleted from DB for project {project_id}")
                    else:
                        LOG.info(f"No config found to delete for project {project_id}")
                    return deleted
                finally:
                    cursor.close()
                    conn.close()
            except Exception as e:
                LOG.error(f"Failed to delete config from DB for project {project_id}: {e}")
                raise

        try:
            loop = asyncio.get_event_loop()
            deleted = await loop.run_in_executor(None, _delete_sync)
            # Invalidate cache after deletion
            if deleted:
                self.invalidate_cache(project_id)
            return deleted
        except Exception as e:
            LOG.error(f"Failed to delete config for project {project_id}: {e}")
            raise
