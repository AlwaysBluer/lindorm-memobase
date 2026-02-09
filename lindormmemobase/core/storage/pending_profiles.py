"""PendingProfiles storage for subtopic-level merge strategy.

This module provides storage for extracted profiles that haven't reached merge threshold yet.
Part of feature 001-profile-merge-strategy.

Table Schema:
    CREATE TABLE PendingProfiles (
        entry_id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(128) NOT NULL,
        project_id VARCHAR(64),
        topic VARCHAR(128) NOT NULL,
        subtopic VARCHAR(128) NOT NULL,
        profile_content TEXT NOT NULL,
        profile_attributes JSON,
        pending_count INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_user_topic (user_id, topic, subtopic),
        INDEX idx_project (project_id)
    ) PARTITION BY HASH(user_id) PARTITIONS 16;
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from lindormmemobase.config import Config, LOG
from lindormmemobase.utils.errors import TableStorageError
from .base import LindormStorageBase


class PendingProfiles(LindormStorageBase):
    """Storage for pending profiles awaiting merge threshold.

    This class manages the PendingProfiles table which stores extracted profiles
    that haven't reached the configured merge threshold yet.

    Key operations:
    - Store extracted profiles when threshold > 1
    - Track pending count per (user_id, topic, subtopic, project_id)
    - Retrieve pending entries for merge operations
    - Clean up entries after successful merge
    """

    def __init__(self, config: Config):
        """Initialize PendingProfiles storage.

        Args:
            config: Configuration object containing connection parameters
        """
        super().__init__(config)

    def _get_pool_name(self) -> str:
        """Return unique pool name for pending profiles storage.

        Returns:
            Pool name string
        """
        return "pending_profiles_pool"

    def _get_pool_config(self) -> dict:
        """Return connection pool configuration for pending profiles storage.

        Returns:
            Dictionary with pool configuration
        """
        return {
            'host': self.config.lindorm_table_host,
            'port': self.config.lindorm_table_port,
            'user': self.config.lindorm_table_username,
            'password': self.config.lindorm_table_password,
            'database': self.config.lindorm_table_database,
            'pool_size': self.config.lindorm_table_pool_size
        }

    def initialize_tables(self):
        """Create PendingProfiles table.

        This method is called during StorageManager initialization.
        Uses SHOW TABLES LIKE for fast existence check (~0.05s vs ~20s).

        Note: This is a synchronous method. Call during initialization phase only.
        """
        self._create_table()

    def _create_table(self):
        """Create PendingProfiles table via SQL.

        Uses Lindorm's SHOW TABLES LIKE for fast existence checking.
        Table is hash partitioned by user_id (16 partitions).

        Raises:
            TableStorageError: If table creation fails
        """
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()

            # Check if table exists using Lindorm's SHOW TABLES (much faster than IF NOT EXISTS)
            cursor.execute("SHOW TABLES LIKE 'PendingProfiles'")
            if cursor.fetchone():
                LOG.info("PendingProfiles table already exists, skipping creation")
                return

            # Create table
            cursor.execute("""
                CREATE TABLE PendingProfiles (
                    entry_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    project_id VARCHAR(64),
                    topic VARCHAR(128) NOT NULL,
                    subtopic VARCHAR(128) NOT NULL,
                    profile_content TEXT NOT NULL,
                    profile_attributes JSON,
                    pending_count INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_topic (user_id, topic, subtopic),
                    INDEX idx_project (project_id)
                ) PARTITION BY HASH(user_id) PARTITIONS 16
            """)

            conn.commit()
            LOG.info("PendingProfiles table created")
        except Exception as e:
            conn.rollback()
            raise TableStorageError(f"Failed to create PendingProfiles table: {str(e)}") from e
        finally:
            cursor.close()
            conn.close()

    async def insert_pending(
        self,
        user_id: str,
        topic: str,
        subtopic: str,
        profile_content: str,
        profile_attributes: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        pending_count: int = 1
    ) -> str:
        """Insert a new pending profile entry.

        Args:
            user_id: User identifier
            topic: Topic name
            subtopic: Subtopic name
            profile_content: Extracted profile content
            profile_attributes: Optional metadata attributes
            project_id: Optional project identifier for multi-tenancy
            pending_count: Current pending count (default: 1)

        Returns:
            entry_id: UUID of the created entry

        Raises:
            TableStorageError: If insertion fails
        """
        import json

        def _insert_pending_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                entry_id = str(uuid.uuid4())
                # Use configured timezone, strip tzinfo for Lindorm TIMESTAMP
                now = datetime.now(self.config.timezone).replace(tzinfo=None)

                # Convert profile_attributes to JSON string if provided
                attributes_json = json.dumps(profile_attributes) if profile_attributes else None

                cursor.execute(
                    """
                    INSERT INTO PendingProfiles
                    (entry_id, user_id, project_id, topic, subtopic, profile_content, profile_attributes, pending_count, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (entry_id, str(user_id), str(project_id) if project_id else None,
                     str(topic), str(subtopic), str(profile_content), attributes_json,
                     pending_count, now, now)
                )
                conn.commit()
                return entry_id
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(
            _insert_pending_sync,
            "Failed to insert pending profile"
        )

    async def get_pending_count(
        self,
        user_id: str,
        topic: str,
        subtopic: str,
        project_id: Optional[str] = None
    ) -> int:
        """Get count of pending profiles for given parameters.

        Args:
            user_id: User identifier
            topic: Topic name
            subtopic: Subtopic name
            project_id: Optional project identifier

        Returns:
            Count of pending profiles matching the criteria

        Raises:
            TableStorageError: If query fails
        """
        def _get_pending_count_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()

                if project_id is not None:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM PendingProfiles
                        WHERE user_id = %s AND topic = %s AND subtopic = %s AND project_id = %s
                        """,
                        (str(user_id), str(topic), str(subtopic), str(project_id))
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM PendingProfiles
                        WHERE user_id = %s AND topic = %s AND subtopic = %s AND project_id IS NULL
                        """,
                        (str(user_id), str(topic), str(subtopic))
                    )

                result = cursor.fetchone()
                return result[0] if result else 0
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(
            _get_pending_count_sync,
            "Failed to get pending count"
        )

    async def get_pending_entries(
        self,
        user_id: str,
        topic: Optional[str] = None,
        subtopic: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get pending entries for merge operation.

        Args:
            user_id: User identifier (required)
            topic: Optional topic filter
            subtopic: Optional subtopic filter
            project_id: Optional project filter
            limit: Optional maximum number of entries to return

        Returns:
            List of pending profile entries with all fields

        Raises:
            TableStorageError: If query fails
        """
        import json

        def _get_pending_entries_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor(dictionary=True)

                # Build query with optional filters
                query = """
                    SELECT entry_id, user_id, project_id, topic, subtopic,
                           profile_content, profile_attributes, pending_count,
                           created_at, updated_at
                    FROM PendingProfiles
                    WHERE user_id = %s
                """
                params = [str(user_id)]

                if topic is not None:
                    query += " AND topic = %s"
                    params.append(str(topic))

                if subtopic is not None:
                    query += " AND subtopic = %s"
                    params.append(str(subtopic))

                if project_id is not None:
                    query += " AND project_id = %s"
                    params.append(str(project_id))

                # Order by created_at ASC (oldest first for merge)
                query += " ORDER BY created_at ASC"

                if limit is not None:
                    query += " LIMIT %s"
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Parse JSON attributes and format results
                entries = []
                for row in rows:
                    entry = {
                        'entry_id': row['entry_id'],
                        'user_id': row['user_id'],
                        'project_id': row.get('project_id'),
                        'topic': row['topic'],
                        'subtopic': row['subtopic'],
                        'profile_content': row['profile_content'],
                        'profile_attributes': json.loads(row['profile_attributes']) if row.get('profile_attributes') else None,
                        'pending_count': row['pending_count'],
                        'created_at': row['created_at'].isoformat() if row.get('created_at') else None,
                        'updated_at': row['updated_at'].isoformat() if row.get('updated_at') else None,
                    }
                    entries.append(entry)

                return entries
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(
            _get_pending_entries_sync,
            "Failed to get pending entries"
        )

    async def delete_pending_entries(
        self,
        entry_ids: List[str]
    ) -> int:
        """Delete pending entries after successful merge.

        Args:
            entry_ids: List of entry IDs to delete

        Returns:
            Number of entries deleted

        Raises:
            TableStorageError: If deletion fails
        """
        if not entry_ids:
            return 0

        def _delete_pending_entries_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()

                # Build placeholder string for IN clause
                placeholders = ', '.join(['%s'] * len(entry_ids))

                cursor.execute(
                    f"DELETE FROM PendingProfiles WHERE entry_id IN ({placeholders})",
                    entry_ids
                )

                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(
            _delete_pending_entries_sync,
            "Failed to delete pending entries"
        )

    async def check_pending_limit(
        self,
        user_id: str,
        topic: str,
        subtopic: str,
        project_id: Optional[str] = None,
        max_pending: Optional[int] = None
    ) -> Tuple[bool, int]:
        """Check if pending limit is exceeded.

        Args:
            user_id: User identifier
            topic: Topic name
            subtopic: Subtopic name
            project_id: Optional project identifier
            max_pending: Maximum allowed pending profiles (uses config default if None)

        Returns:
            Tuple of (is_exceeded: bool, current_count: int)

        Raises:
            PendingLimitExceededError: If limit is exceeded
            TableStorageError: If query fails
        """
        from lindormmemobase.utils.errors import PendingLimitExceededError

        # Use provided max_pending or default from config
        if max_pending is None:
            max_pending = self.config.max_pending_profiles

        # Get current count
        current_count = await self.get_pending_count(user_id, topic, subtopic, project_id)

        # Check if exceeded
        is_exceeded = current_count >= max_pending

        if is_exceeded:
            raise PendingLimitExceededError(
                f"Maximum {max_pending} pending profiles exceeded "
                f"(current: {current_count}) for user={user_id}, topic={topic}, subtopic={subtopic}"
            )

        return (is_exceeded, current_count)

    async def reset(
        self,
        user_id: str,
        project_id: Optional[str] = None
    ) -> int:
        """Reset pending profiles for a user.

        This method deletes all pending profile entries for a specific user,
        optionally filtered by project_id. Used during user data cleanup.

        Args:
            user_id: User identifier
            project_id: Optional project identifier filter

        Returns:
            Number of pending profile entries deleted

        Raises:
            TableStorageError: If deletion fails
        """
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()

                if project_id is not None:
                    cursor.execute(
                        """
                        DELETE FROM PendingProfiles
                        WHERE user_id = %s AND project_id = %s
                        """,
                        (str(user_id), str(project_id))
                    )
                else:
                    cursor.execute(
                        """
                        DELETE FROM PendingProfiles
                        WHERE user_id = %s
                        """,
                        (str(user_id),)
                    )

                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(
            _reset_sync,
            "Failed to reset pending profiles"
        )
