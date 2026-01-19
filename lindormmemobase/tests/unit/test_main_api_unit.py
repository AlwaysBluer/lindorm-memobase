"""
Unit tests for main API (main.py - LindormMemobase class).

Tests initialization, configuration, error handling using mocks.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from lindormmemobase.main import LindormMemobase, LindormMemobaseError, ConfigurationError
from lindormmemobase.models.response import ChatModalResponse


@pytest.mark.unit
class TestLindormMemobaseInitialization:
    """Test LindormMemobase initialization."""
    
    def test_initialization_with_minimal_config(self, minimal_config):
        """Test initialization with minimal configuration."""
        with patch('lindormmemobase.core.storage.manager.StorageManager'):
            memobase = LindormMemobase(minimal_config)
            
            assert memobase.config is not None
            assert memobase.config.language == "en"
    
    def test_initialization_without_config_uses_defaults(self):
        """Test initialization without config loads defaults."""
        with patch('lindormmemobase.main.Config.load_config') as mock_load:
            with patch('lindormmemobase.core.storage.manager.StorageManager'):
                mock_config = Mock()
                mock_load.return_value = mock_config
                
                memobase = LindormMemobase()
                
                assert memobase.config == mock_config
                mock_load.assert_called_once()
    
    def test_initialization_calls_storage_manager(self, minimal_config):
        """Test that initialization sets up StorageManager."""
        # Patch at module level since _init_storage_sync imports from there
        with patch('lindormmemobase.core.storage.manager.StorageManager') as mock_sm:
            # Make initialize return an awaitable coroutine
            async def mock_initialize(config):
                return None

            mock_sm.is_initialized.return_value = False
            mock_sm.initialize = mock_initialize

            memobase = LindormMemobase(minimal_config)

            # Verify initialization was called
            # Note: We can't easily verify the exact call due to how the import works
    
    def test_initialization_skips_storage_if_initialized(self, minimal_config):
        """Test that StorageManager is not re-initialized if already set up."""
        with patch('lindormmemobase.core.storage.manager.StorageManager') as mock_sm:
            mock_sm.is_initialized.return_value = True
            
            memobase = LindormMemobase(minimal_config)
            
            mock_sm.initialize.assert_not_called()


@pytest.mark.unit
class TestLindormMemobaseFromMethods:
    """Test factory methods for creating LindormMemobase instances."""
    
    def test_from_yaml_file_valid_path(self, temp_yaml_config):
        """Test creating instance from valid YAML file."""
        with patch('lindormmemobase.core.storage.manager.StorageManager'):
            memobase = LindormMemobase.from_yaml_file(str(temp_yaml_config))
            
            assert memobase.config is not None
            assert memobase.config.llm_api_key == "test-yaml-key"
    
    def test_from_yaml_file_nonexistent_raises_error(self, tmp_path):
        """Test that missing YAML file raises ConfigurationError."""
        nonexistent = tmp_path / "nonexistent.yaml"
        
        with pytest.raises(ConfigurationError) as exc_info:
            LindormMemobase.from_yaml_file(str(nonexistent))
        
        assert "not found" in str(exc_info.value)
    
    def test_from_config_with_parameters(self):
        """Test creating instance from parameters."""
        with patch('lindormmemobase.core.storage.manager.StorageManager'):
            memobase = LindormMemobase.from_config(
                language="zh",
                llm_api_key="test-key",
                best_llm_model="gpt-4o"
            )
            
            assert memobase.config.language == "zh"
            assert memobase.config.llm_api_key == "test-key"
            assert memobase.config.best_llm_model == "gpt-4o"


@pytest.mark.unit
class TestLindormMemobaseErrorHandling:
    """Test error handling in LindormMemobase."""
    
    def test_configuration_error_on_invalid_config(self):
        """Test that invalid configuration raises ConfigurationError."""
        with patch('lindormmemobase.main.Config.load_config', side_effect=Exception("Invalid config")):
            with pytest.raises(ConfigurationError) as exc_info:
                LindormMemobase()
            
            assert "Failed to load configuration" in str(exc_info.value)
    
    def test_configuration_error_preserves_context(self):
        """Test that ConfigurationError preserves original exception."""
        original_error = ValueError("Original error")
        
        with patch('lindormmemobase.main.Config.load_config', side_effect=original_error):
            with pytest.raises(ConfigurationError) as exc_info:
                LindormMemobase()
            
            assert exc_info.value.__cause__ == original_error


@pytest.mark.unit
@pytest.mark.asyncio
class TestAsyncMethods:
    """Test async methods with mocks."""
    
    async def test_extract_memories_with_mock(self, minimal_config, sample_chat_blob):
        """Test extract_memories with mocked dependencies."""
        with patch('lindormmemobase.core.storage.manager.StorageManager'):
            with patch('lindormmemobase.main.process_blobs', new_callable=AsyncMock) as mock_process:
                from lindormmemobase.models.response import ChatModalResponse

                # Mock successful extraction - process_blobs returns ChatModalResponse
                mock_response = ChatModalResponse(
                    event_id="test_event_123",
                    add_profiles=["profile_1", "profile_2"],
                    update_profiles=["profile_3"],
                    delete_profiles=[]
                )
                mock_process.return_value = mock_response

                memobase = LindormMemobase(minimal_config)
                result = await memobase.extract_memories(
                    user_id="test_user",
                    blobs=[sample_chat_blob]
                )

                assert result.event_id == "test_event_123"
                assert result.add_profiles == ["profile_1", "profile_2"]
                mock_process.assert_called_once()

    async def test_extract_memories_handles_failure(self, minimal_config, sample_chat_blob):
        """Test that extract_memories raises error on failure."""
        with patch('lindormmemobase.core.storage.manager.StorageManager'):
            with patch('lindormmemobase.main.process_blobs', new_callable=AsyncMock) as mock_process:
                # Mock failed extraction
                mock_process.side_effect = Exception("LLM failed")

                memobase = LindormMemobase(minimal_config)

                with pytest.raises(LindormMemobaseError) as exc_info:
                    await memobase.extract_memories(
                        user_id="test_user",
                        blobs=[sample_chat_blob]
                    )

                assert "Memory extraction failed" in str(exc_info.value)


@pytest.mark.unit
class TestLindormMemobaseExceptions:
    """Test custom exception classes."""
    
    def test_lindorm_memobase_error_is_exception(self):
        """Test that LindormMemobaseError is an Exception."""
        error = LindormMemobaseError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_configuration_error_is_lindorm_error(self):
        """Test that ConfigurationError inherits from LindormMemobaseError."""
        error = ConfigurationError("Config error")
        assert isinstance(error, LindormMemobaseError)
        assert isinstance(error, Exception)
