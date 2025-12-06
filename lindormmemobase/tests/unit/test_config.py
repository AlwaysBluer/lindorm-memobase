"""
Unit tests for configuration (config/__init__.py).

Tests configuration loading, validation, environment variable processing.
"""

import os
import pytest
import tempfile
from pathlib import Path

from lindormmemobase.config import Config


@pytest.mark.unit
class TestConfigCreation:
    """Test basic Config creation and defaults."""
    
    def test_config_creation_with_defaults(self):
        """Test creating config with default values."""
        config = Config(
            llm_api_key="test-key",
            lindorm_table_host="localhost",
            lindorm_search_host="localhost"
        )
        
        assert config.llm_api_key == "test-key"
        assert config.language == "en"
        assert config.best_llm_model == "gpt-4o-mini"
    
    def test_config_required_fields(self):
        """Test that config can be created with minimal fields."""
        config = Config(enable_event_embedding=False)
        
        # Defaults should be set
        assert config.language == "en"
        assert config.llm_style == "openai"
        assert config.embedding_provider == "openai"
    
    def test_config_custom_language(self):
        """Test setting custom language."""
        config = Config(language="zh", enable_event_embedding=False)
        
        assert config.language == "zh"
    
    def test_config_custom_llm_model(self):
        """Test setting custom LLM model."""
        config = Config(best_llm_model="gpt-4o", enable_event_embedding=False)
        
        assert config.best_llm_model == "gpt-4o"
    
    def test_config_embedding_dimensions(self):
        """Test embedding dimension configuration."""
        config = Config(embedding_dim=768, enable_event_embedding=False)
        
        assert config.embedding_dim == 768


@pytest.mark.unit
class TestConfigFromYAML:
    """Test loading config from YAML files."""
    
    def test_load_from_yaml_file(self, temp_yaml_config):
        """Test loading config from YAML file."""
        config = Config.from_yaml_file(str(temp_yaml_config))
        
        assert config.llm_api_key == "test-yaml-key"
        assert config.llm_base_url == "http://yaml-test-server"
        assert config.lindorm_table_username == "yaml_user"
    
    def test_load_from_nonexistent_yaml(self, tmp_path, monkeypatch):
        """Test loading from nonexistent YAML file returns defaults."""
        monkeypatch.setenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "false")
        nonexistent = tmp_path / "nonexistent.yaml"
        config = Config.from_yaml_file(str(nonexistent))
        
        # Should return config with defaults
        assert config.language == "en"
    
    def test_yaml_overrides_defaults(self, tmp_path):
        """Test that YAML values override defaults."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("""
language: zh
best_llm_model: custom-model
embedding_dim: 512
enable_event_embedding: false
""")
        
        config = Config.from_yaml_file(str(yaml_file))
        
        assert config.language == "zh"
        assert config.best_llm_model == "custom-model"
        assert config.embedding_dim == 512


@pytest.mark.unit
class TestConfigEnvironmentVariables:
    """Test environment variable processing."""
    
    def test_env_var_override(self, tmp_path, monkeypatch):
        """Test that environment variables override config."""
        # Set environment variable
        monkeypatch.setenv("MEMOBASE_LANGUAGE", "zh")
        monkeypatch.setenv("MEMOBASE_BEST_LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "false")
        
        # Create empty YAML
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("language: en\n")
        
        config = Config.from_yaml_file(str(yaml_file))
        
        # Env var should override YAML
        assert config.language == "zh"
        assert config.best_llm_model == "gpt-4o"
    
    def test_env_var_integer_parsing(self, monkeypatch):
        """Test parsing integer from environment variable."""
        monkeypatch.setenv("MEMOBASE_EMBEDDING_DIM", "768")
        monkeypatch.setenv("MEMOBASE_LINDORM_TABLE_PORT", "33061")
        monkeypatch.setenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "false")
        
        config = Config.from_yaml_file("/nonexistent/path")
        
        assert config.embedding_dim == 768
        assert config.lindorm_table_port == 33061
    
    def test_env_var_boolean_parsing(self, monkeypatch):
        """Test parsing boolean from environment variable."""
        monkeypatch.setenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "true")
        monkeypatch.setenv("MEMOBASE_PROFILE_STRICT_MODE", "false")
        monkeypatch.setenv("MEMOBASE_LLM_API_KEY", "test-key")  # Required when enable_event_embedding=true
        
        config = Config.from_yaml_file("/nonexistent/path")
        
        assert config.enable_event_embedding is True
        assert config.profile_strict_mode is False
    
    def test_env_var_json_parsing(self, monkeypatch):
        """Test parsing JSON from environment variable."""
        monkeypatch.setenv("MEMOBASE_EVENT_TAGS", '[{"tag": "test", "value": "value"}]')
        monkeypatch.setenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "false")
        
        config = Config.from_yaml_file("/nonexistent/path")
        
        assert isinstance(config.event_tags, list)
        assert len(config.event_tags) > 0


@pytest.mark.unit
class TestConfigValidation:
    """Test configuration validation."""
    
    def test_language_literal_validation(self):
        """Test that language accepts only valid values."""
        # Valid languages
        config_en = Config(language="en", enable_event_embedding=False)
        config_zh = Config(language="zh", enable_event_embedding=False)
        
        assert config_en.language == "en"
        assert config_zh.language == "zh"
    
    def test_llm_style_validation(self):
        """Test LLM style validation."""
        config_openai = Config(llm_style="openai", enable_event_embedding=False)
        config_lindorm = Config(llm_style="lindormai", enable_event_embedding=False)
        
        assert config_openai.llm_style == "openai"
        assert config_lindorm.llm_style == "lindormai"
    
    def test_embedding_provider_validation(self):
        """Test embedding provider validation."""
        providers = ["openai", "jina", "lindormai"]
        
        for provider in providers:
            config = Config(embedding_provider=provider, enable_event_embedding=False)
            assert config.embedding_provider == provider


@pytest.mark.unit
class TestConfigPostInit:
    """Test __post_init__ processing."""
    
    def test_embedding_api_key_defaults_to_llm_key(self):
        """Test that embedding API key defaults to LLM API key."""
        config = Config(
            llm_api_key="llm-key-123",
            llm_style="openai",
            embedding_provider="openai",
            enable_event_embedding=True
        )
        
        # Should default to llm_api_key
        assert config.embedding_api_key == "llm-key-123"
    
    def test_embedding_base_url_defaults_to_llm_url(self):
        """Test that embedding base URL defaults to LLM base URL."""
        config = Config(
            llm_api_key="key",
            llm_base_url="http://llm-server",
            llm_style="openai",
            embedding_provider="openai",
            enable_event_embedding=True
        )
        
        assert config.embedding_base_url == "http://llm-server"
    
    def test_jina_embedding_base_url(self):
        """Test Jina embedding base URL default."""
        config = Config(
            embedding_provider="jina",
            embedding_api_key="jina-key",
            embedding_model="jina-embeddings-v3",
            enable_event_embedding=True
        )
        
        assert "jina.ai" in config.embedding_base_url


@pytest.mark.unit
class TestConfigDatabaseSettings:
    """Test database configuration."""
    
    def test_lindorm_table_configuration(self):
        """Test Lindorm table configuration."""
        config = Config(
            lindorm_table_host="table-host",
            lindorm_table_port=33060,
            lindorm_table_username="user",
            lindorm_table_password="pass",
            lindorm_table_database="memobase",
            enable_event_embedding=False
        )
        
        assert config.lindorm_table_host == "table-host"
        assert config.lindorm_table_port == 33060
        assert config.lindorm_table_username == "user"
        assert config.lindorm_table_password == "pass"
        assert config.lindorm_table_database == "memobase"
    
    def test_lindorm_search_configuration(self):
        """Test Lindorm search configuration."""
        config = Config(
            lindorm_search_host="search-host",
            lindorm_search_port=30070,
            lindorm_search_username="search_user",
            lindorm_search_password="search_pass",
            enable_event_embedding=False
        )
        
        assert config.lindorm_search_host == "search-host"
        assert config.lindorm_search_port == 30070
        assert config.lindorm_search_username == "search_user"
        assert config.lindorm_search_password == "search_pass"
    
    def test_buffer_storage_defaults_to_table_config(self):
        """Test that buffer storage defaults to table config."""
        config = Config(
            lindorm_table_host="table-host",
            lindorm_table_port=33060,
            lindorm_table_username="user",
            lindorm_table_password="pass",
            enable_event_embedding=False
        )
        
        # Buffer should be None, falling back to table config
        assert config.lindorm_buffer_host is None
        assert config.lindorm_buffer_port is None


@pytest.mark.unit
class TestConfigSpecialSettings:
    """Test special configuration settings."""
    
    def test_buffer_token_sizes(self):
        """Test buffer token size configuration."""
        config = Config(
            max_chat_blob_buffer_token_size=4096,
            max_chat_blob_buffer_process_token_size=8192,
            enable_event_embedding=False
        )
        
        assert config.max_chat_blob_buffer_token_size == 4096
        assert config.max_chat_blob_buffer_process_token_size == 8192
    
    def test_profile_configuration(self):
        """Test profile-related configuration."""
        config = Config(
            max_profile_subtopics=10,
            profile_strict_mode=True,
            profile_validate_mode=False,
            enable_event_embedding=False
        )
        
        assert config.max_profile_subtopics == 10
        assert config.profile_strict_mode is True
        assert config.profile_validate_mode is False
    
    def test_userprofilesv2_configuration(self):
        """Test UserProfilesV2-specific configuration."""
        config = Config(
            default_project_id="my_project",
            enable_profile_splitting=False,
            profile_split_delimiter="; ",
            enable_event_embedding=False
        )
        
        assert config.default_project_id == "my_project"
        assert config.enable_profile_splitting is False
        assert config.profile_split_delimiter == "; "
    
    def test_test_skip_persist(self):
        """Test test_skip_persist flag."""
        config = Config(test_skip_persist=True, enable_event_embedding=False)
        
        assert config.test_skip_persist is True


@pytest.mark.unit
class TestConfigFixtures:
    """Test config fixtures from conftest."""
    
    def test_minimal_config_fixture(self, minimal_config):
        """Test minimal_config fixture."""
        assert minimal_config.llm_api_key is not None
        assert minimal_config.language == "en"
        assert minimal_config.test_skip_persist is True
    
    def test_mock_config_fixture(self, mock_config):
        """Test mock_config fixture."""
        assert "mock" in mock_config.llm_api_key
        assert mock_config.embedding_dim == 1536
        assert mock_config.test_skip_persist is True
    
    def test_zh_config_fixture(self, zh_config):
        """Test Chinese language config fixture."""
        assert zh_config.language == "zh"
    
    def test_integration_config_fixture(self, integration_config):
        """Test integration config fixture."""
        # Should have database configuration
        assert integration_config.lindorm_table_host is not None
        assert integration_config.lindorm_search_host is not None
