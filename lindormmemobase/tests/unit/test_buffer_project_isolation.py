"""
Unit tests for buffer project_id isolation.

Tests that buffer operations correctly isolate data by project_id,
ensuring proper multi-tenancy support in the buffer subsystem.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from lindormmemobase.core.storage.buffers import (
    LindormBufferStorage,
    insert_blob_to_buffer,
    detect_buffer_full_or_not,
    flush_buffer,
    flush_buffer_by_ids,
    get_buffer_capacity,
    get_unprocessed_buffer_ids,
)
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.core.storage.user_profiles import DEFAULT_PROJECT_ID
from lindormmemobase.config import Config


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = Mock(spec=Config)
    config.default_project_id = "test_default_project"
    config.max_chat_blob_buffer_token_size = 1000
    config.lindorm_buffer_host = "localhost"
    config.lindorm_buffer_port = 3306
    config.lindorm_buffer_username = "test"
    config.lindorm_buffer_password = "test"
    config.lindorm_buffer_database = "test_db"
    return config


@pytest.fixture
def sample_chat_blob():
    """Create a sample chat blob for testing."""
    return ChatBlob(
        messages=[
            OpenAICompatibleMessage(role="user", content="Hello world"),
            OpenAICompatibleMessage(role="assistant", content="Hi there!"),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )


@pytest.mark.unit
class TestLindormBufferStorageProjectIsolation:
    """Test LindormBufferStorage with project_id isolation."""
    
    def test_initialize_tables_includes_project_id_column(self, mock_config):
        """Test that table initialization includes project_id column."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            storage.initialize_tables()
            
            # Verify SQL contains project_id
            sql_call = mock_cursor.execute.call_args[0][0]
            assert "project_id VARCHAR(255) NOT NULL" in sql_call
            assert "PRIMARY KEY(user_id, project_id, blob_id)" in sql_call
    
    @pytest.mark.asyncio
    async def test_insert_blob_with_explicit_project_id(self, mock_config, sample_chat_blob):
        """Test inserting blob with explicit project_id."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.insert_blob(
                user_id="user123",
                blob_id="blob456",
                blob_data=sample_chat_blob,
                project_id="project_alpha"
            )
            
            assert result.ok()
            
            # Verify project_id is in the INSERT
            sql_call = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert "project_id" in sql_call
            assert params[1] == "project_alpha"  # project_id is second param
    
    @pytest.mark.asyncio
    async def test_insert_blob_uses_default_project_id(self, mock_config, sample_chat_blob):
        """Test inserting blob without project_id uses default."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.insert_blob(
                user_id="user123",
                blob_id="blob456",
                blob_data=sample_chat_blob,
                project_id=None
            )
            
            assert result.ok()
            
            # Verify default project_id is used
            params = mock_cursor.execute.call_args[0][1]
            assert params[1] == "test_default_project"
    
    @pytest.mark.asyncio
    async def test_insert_blob_falls_back_to_constant_default(self, sample_chat_blob):
        """Test inserting blob falls back to DEFAULT_PROJECT_ID constant."""
        config = Mock(spec=Config)
        config.default_project_id = None  # No default in config
        config.lindorm_buffer_host = "localhost"
        config.lindorm_buffer_port = 3306
        config.lindorm_buffer_username = "test"
        config.lindorm_buffer_password = "test"
        config.lindorm_buffer_database = "test_db"
        config.lindorm_table_host = "localhost"
        config.lindorm_table_port = 3306
        config.lindorm_table_username = "test"
        config.lindorm_table_password = "test"
        config.lindorm_table_database = "test_db"
        
        storage = LindormBufferStorage(config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.insert_blob(
                user_id="user123",
                blob_id="blob456",
                blob_data=sample_chat_blob,
                project_id=None
            )
            
            assert result.ok()
            
            # Verify DEFAULT_PROJECT_ID constant is used
            params = mock_cursor.execute.call_args[0][1]
            assert params[1] == DEFAULT_PROJECT_ID
    
    @pytest.mark.asyncio
    async def test_get_capacity_filters_by_project_id(self, mock_config):
        """Test get_capacity filters by project_id."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.get_capacity(
                user_id="user123",
                blob_type=BlobType.chat,
                project_id="project_alpha"
            )
            
            assert result.ok()
            assert result.data() == 5
            
            # Verify project_id in WHERE clause
            sql_call = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert "project_id = %s" in sql_call
            assert "project_alpha" in params
    
    @pytest.mark.asyncio
    async def test_check_overflow_scoped_to_project(self, mock_config):
        """Test check_overflow is scoped to specific project_id."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Simulate overflow: total tokens > max
        mock_cursor.fetchall.return_value = [
            ("blob1", 600),
            ("blob2", 500),
        ]
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.check_overflow(
                user_id="user123",
                blob_type=BlobType.chat,
                max_tokens=1000,
                project_id="project_beta"
            )
            
            assert result.ok()
            blob_ids = result.data()
            assert len(blob_ids) == 2  # Overflow detected
            
            # Verify project_id filtering
            params = mock_cursor.execute.call_args[0][1]
            assert "project_beta" in params
    
    @pytest.mark.asyncio
    async def test_get_ids_by_status_isolates_by_project(self, mock_config):
        """Test get_ids_by_status isolates by project_id."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("blob1",), ("blob2",)]
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result = await storage.get_ids_by_status(
                user_id="user123",
                blob_type=BlobType.chat,
                status="idle",
                project_id="project_gamma"
            )
            
            assert result.ok()
            assert result.data() == ["blob1", "blob2"]
            
            # Verify project_id in query
            sql_call = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert "project_id = %s" in sql_call
            assert "project_gamma" in params
    
    @pytest.mark.asyncio
    async def test_load_blobs_filters_by_project_id(self, mock_config):
        """Test _load_blobs filters by project_id."""
        storage = LindormBufferStorage(mock_config)
        
        blob_data = {
            "messages": [{"role": "user", "content": "test"}],
            "type": "chat"
        }
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("blob1", "chat", '{"messages": [{"role": "user", "content": "test"}], "type": "chat"}')
        ]
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            blobs = await storage._load_blobs(
                user_id="user123",
                blob_ids=["blob1"],
                project_id="project_delta"
            )
            
            assert len(blobs) == 1
            
            # Verify project_id in SQL
            sql_call = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert "project_id = %s" in sql_call
            assert params[0] == "user123"
            assert params[1] == "project_delta"
    
    @pytest.mark.asyncio
    async def test_update_status_includes_project_id(self, mock_config):
        """Test _update_status includes project_id in WHERE clause."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            await storage._update_status(
                user_id="user123",
                blob_ids=["blob1", "blob2"],
                status="done",
                project_id="project_epsilon"
            )
            
            # Verify UPDATE includes project_id (batch UPDATE with IN clause)
            sql, params = mock_cursor.execute.call_args[0]
            assert "project_id = %s" in sql
            assert "project_epsilon" in params
            assert "blob_id IN" in sql


@pytest.mark.unit
@pytest.mark.asyncio
class TestBufferAPIProjectIsolation:
    """Test buffer API functions with project_id isolation."""
    
    async def test_insert_blob_to_buffer_with_project_id(self, mock_config, sample_chat_blob):
        """Test insert_blob_to_buffer propagates project_id."""
        with patch('lindormmemobase.core.storage.buffers.create_buffer_storage') as mock_create:
            mock_storage = Mock()
            mock_storage.insert_blob = AsyncMock(return_value=Mock(ok=lambda: True))
            mock_create.return_value = mock_storage
            
            await insert_blob_to_buffer(
                user_id="user123",
                blob_id="blob456",
                blob_data=sample_chat_blob,
                config=mock_config,
                project_id="project_zeta"
            )
            
            # Verify project_id was passed
            mock_storage.insert_blob.assert_called_once()
            call_args = mock_storage.insert_blob.call_args[0]
            # project_id is the 4th positional argument (index 3)
            assert len(call_args) == 4
            assert call_args[3] == "project_zeta"
    
    async def test_detect_buffer_full_with_project_id(self, mock_config):
        """Test detect_buffer_full_or_not uses project_id."""
        with patch('lindormmemobase.core.storage.buffers.create_buffer_storage') as mock_create:
            mock_storage = Mock()
            mock_storage.check_overflow = AsyncMock(return_value=Mock(ok=lambda: True, data=lambda: []))
            mock_create.return_value = mock_storage
            
            await detect_buffer_full_or_not(
                user_id="user123",
                blob_type=BlobType.chat,
                config=mock_config,
                project_id="project_eta"
            )
            
            # Verify project_id was passed
            mock_storage.check_overflow.assert_called_once()
            call_args = mock_storage.check_overflow.call_args[0]
            assert call_args[3] == "project_eta"
    
    async def test_flush_buffer_propagates_project_id(self, mock_config):
        """Test flush_buffer propagates project_id to process_blobs."""
        with patch('lindormmemobase.core.storage.buffers.create_buffer_storage') as mock_create:
            mock_storage = Mock()
            mock_result = Mock(ok=lambda: True, data=lambda: ["blob1"])
            mock_storage.get_ids_by_status = AsyncMock(return_value=mock_result)
            mock_storage.flush = AsyncMock(return_value=Mock(ok=lambda: True))
            mock_create.return_value = mock_storage
            
            await flush_buffer(
                user_id="user123",
                blob_type=BlobType.chat,
                config=mock_config,
                profile_config=None,
                project_id="project_theta"
            )
            
            # Verify flush was called with project_id
            mock_storage.flush.assert_called_once()
            call_args = mock_storage.flush.call_args[0]
            # project_id should be in kwargs or last positional arg
            assert mock_storage.flush.call_args.kwargs.get('project_id') == "project_theta" or \
                   (len(call_args) > 5 and call_args[5] == "project_theta")


@pytest.mark.unit
@pytest.mark.asyncio
class TestCrossProjectIsolation:
    """Test that different projects are properly isolated in buffer."""
    
    async def test_projects_have_independent_buffers(self, mock_config, sample_chat_blob):
        """Test that different projects maintain independent buffer state."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            # Insert to project_A
            await storage.insert_blob(
                user_id="user123",
                blob_id="blob_a",
                blob_data=sample_chat_blob,
                project_id="project_A"
            )
            
            # Insert to project_B
            await storage.insert_blob(
                user_id="user123",
                blob_id="blob_b",
                blob_data=sample_chat_blob,
                project_id="project_B"
            )
            
            # Verify two separate INSERT calls with different project_ids
            assert mock_cursor.execute.call_count == 2
            
            call1_params = mock_cursor.execute.call_args_list[0][0][1]
            call2_params = mock_cursor.execute.call_args_list[1][0][1]
            
            assert call1_params[1] == "project_A"
            assert call2_params[1] == "project_B"
    
    async def test_overflow_detection_isolated_per_project(self, mock_config):
        """Test overflow detection is isolated per project."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Project A has overflow
        mock_cursor.fetchall.return_value = [("blob1", 1100)]
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            result_a = await storage.check_overflow(
                user_id="user123",
                blob_type=BlobType.chat,
                max_tokens=1000,
                project_id="project_A"
            )
            
            assert result_a.ok()
            assert len(result_a.data()) > 0  # Overflow in project A
            
            # Project B has no overflow (reset mock)
            mock_cursor.fetchall.return_value = [("blob2", 500)]
            
            result_b = await storage.check_overflow(
                user_id="user123",
                blob_type=BlobType.chat,
                max_tokens=1000,
                project_id="project_B"
            )
            
            assert result_b.ok()
            assert len(result_b.data()) == 0  # No overflow in project B


@pytest.mark.unit
@pytest.mark.asyncio
class TestBackwardCompatibility:
    """Test backward compatibility when project_id is not provided."""
    
    async def test_api_works_without_project_id(self, mock_config, sample_chat_blob):
        """Test that API functions work without providing project_id."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            # Should not raise error
            result = await storage.insert_blob(
                user_id="user123",
                blob_id="blob456",
                blob_data=sample_chat_blob
                # project_id not provided
            )
            
            assert result.ok()
            
            # Should use default project_id
            params = mock_cursor.execute.call_args[0][1]
            assert params[1] == "test_default_project"
    
    async def test_existing_code_continues_to_work(self, mock_config):
        """Test that existing code without project_id continues to function."""
        storage = LindormBufferStorage(mock_config)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_pool.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(storage, '_get_pool', return_value=mock_pool):
            # Old-style call without project_id
            result = await storage.get_capacity(
                user_id="user123",
                blob_type=BlobType.chat
            )
            
            assert result.ok()
            assert result.data() == 3
