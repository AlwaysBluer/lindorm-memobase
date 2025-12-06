"""
Integration tests for main API (LindormMemobase class).

These tests verify end-to-end workflows with real or mocked services.
"""

import pytest
from datetime import datetime
from lindormmemobase.main import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage, BlobType


@pytest.mark.integration
@pytest.mark.asyncio
class TestLindormMemobaseIntegration:
    """Integration tests for LindormMemobase API."""
    
    @pytest.fixture
    def memobase(self, integration_config):
        """Create LindormMemobase instance for testing."""
        return LindormMemobase(integration_config)
    
    async def test_initialization_workflow(self, integration_config):
        """Test complete initialization workflow."""
        # Should initialize without errors
        memobase = LindormMemobase(integration_config)
        
        assert memobase.config is not None
        assert memobase.config.language in ["en", "zh"]
    
    async def test_from_yaml_workflow(self, temp_yaml_config):
        """Test initialization from YAML file."""
        memobase = LindormMemobase.from_yaml_file(str(temp_yaml_config))
        
        assert memobase.config.llm_api_key == "test-yaml-key"
    
    async def test_from_config_workflow(self):
        """Test initialization from parameters."""
        memobase = LindormMemobase.from_config(
            language="en",
            llm_api_key="test-key",
            best_llm_model="gpt-4o-mini",
            test_skip_persist=True
        )
        
        assert memobase.config.language == "en"


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.asyncio
class TestMemoryExtractionIntegration:
    """Integration tests for memory extraction (requires API key)."""
    
    @pytest.fixture
    def memobase(self, integration_config):
        """Create memobase with integration config."""
        return LindormMemobase(integration_config)
    
    @pytest.mark.skip(reason="Requires real LLM API key")
    async def test_extract_memories_from_chat(self, memobase):
        """Test extracting memories from chat blob."""
        chat_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(
                    role="user",
                    content="I love traveling to Japan"
                ),
                OpenAICompatibleMessage(
                    role="assistant",
                    content="That's great! What do you like about Japan?"
                )
            ],
            type=BlobType.chat,
            created_at=datetime.now()
        )
        
        result = await memobase.extract_memories(
            user_id="integration_test_user",
            blobs=[chat_blob]
        )
        
        # Result should contain extraction data
        assert result is not None


@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration handling."""
    
    def test_multiple_initialization_methods(self):
        """Test that different initialization methods work."""
        # Default initialization
        memobase1 = LindormMemobase.from_config(
            llm_api_key="key1",
            test_skip_persist=True
        )
        
        # From parameters
        memobase2 = LindormMemobase.from_config(
            language="zh",
            llm_api_key="key2",
            test_skip_persist=True
        )
        
        assert memobase1.config.language == "en"  # default
        assert memobase2.config.language == "zh"  # custom
