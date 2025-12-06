"""
Pytest configuration and shared fixtures for lindormmemobase tests.

This module provides:
- Test markers configuration
- Shared fixtures for configurations
- Mock implementations
- Test utilities
"""

import os
import pytest
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Import Config and models only when needed to avoid tiktoken initialization issues
# from lindormmemobase.config import Config
# from lindormmemobase.models.blob import ChatBlob, DocBlob, BlobType, OpenAICompatibleMessage
# from lindormmemobase.models.profile_topic import ProfileConfig


# ==================== Pytest Configuration ====================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Fast, isolated unit tests")
    config.addinivalue_line("markers", "integration: Tests requiring external services")
    config.addinivalue_line("markers", "slow: Long-running tests")
    config.addinivalue_line("markers", "requires_api_key: Tests needing real API credentials")
    config.addinivalue_line("markers", "requires_database: Tests needing Lindorm connection")


# ==================== Configuration Fixtures ====================

@pytest.fixture
def minimal_config():
    """
    Provide a minimal configuration for unit tests.
    
    This configuration has the bare minimum settings and doesn't require
    any external services or credentials.
    """
    from lindormmemobase.config import Config
    
    return Config(
        llm_api_key="test-key-12345",
        llm_base_url="http://localhost:8000",
        language="en",
        llm_style="openai",
        best_llm_model="gpt-4o-mini",
        embedding_provider="openai",
        embedding_api_key="test-embedding-key",
        embedding_dim=1536,
        lindorm_table_host="localhost",
        lindorm_table_port=33060,
        lindorm_table_username="test_user",
        lindorm_table_password="test_pass",
        lindorm_table_database="memobase_test",
        lindorm_search_host="localhost",
        lindorm_search_port=30070,
        test_skip_persist=True  # Skip actual persistence in unit tests
    )


@pytest.fixture
def mock_config():
    """
    Provide a configuration with all mock values for testing.
    
    Suitable for unit tests that need a fully configured instance
    without real service connections.
    """
    from lindormmemobase.config import Config
    
    return Config(
        llm_api_key="mock-llm-api-key",
        llm_base_url="http://mock-llm-server",
        language="en",
        llm_style="openai",
        best_llm_model="gpt-4o-mini",
        summary_llm_model="gpt-4o-mini",
        embedding_provider="openai",
        embedding_api_key="mock-embedding-key",
        embedding_base_url="http://mock-embedding-server",
        embedding_dim=1536,
        embedding_model="text-embedding-v3",
        lindorm_table_host="mock-table-host",
        lindorm_table_port=33060,
        lindorm_table_username="mock_user",
        lindorm_table_password="mock_password",
        lindorm_table_database="mock_memobase",
        lindorm_search_host="mock-search-host",
        lindorm_search_port=30070,
        lindorm_search_username="mock_search_user",
        lindorm_search_password="mock_search_pass",
        enable_event_embedding=True,
        test_skip_persist=True,
        max_chat_blob_buffer_token_size=8192,
        max_chat_blob_buffer_process_token_size=16384
    )


@pytest.fixture
def zh_config(mock_config):
    """Provide a Chinese language configuration for testing."""
    mock_config.language = "zh"
    return mock_config


@pytest.fixture(scope="class")
def integration_config():
    """
    Provide configuration for integration tests.
    
    Priority order:
    1. Environment variables (highest)
    2. config.yaml file
    3. Default test values (fallback)
    """
    from lindormmemobase.config import Config
    
    # Try to load from config.yaml file first
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    config_paths = [
        os.path.join(project_root, "config.yaml"),  # Project root
        "config.yaml",                              # Current directory
        os.path.join(os.getcwd(), "config.yaml")    # Workspace root
    ]
    
    config = None
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                config = Config.from_yaml_file(config_path)
                break
            except Exception:
                continue
    
    # If no config file found, create default config
    if config is None:
        config = Config(
            llm_api_key="integration-test-key",
            embedding_api_key="integration-test-embedding-key",
            language="en",
            llm_style="openai",
            best_llm_model="gpt-4o-mini",
            embedding_provider="openai",
            embedding_dim=1536,
            lindorm_table_host="localhost",
            lindorm_table_port=33060,
            lindorm_table_username="root",
            lindorm_table_password="",
            lindorm_table_database="memobase_test",
            lindorm_search_host="localhost",
            lindorm_search_port=30070,
        )
    
    return config


# ==================== Data Model Fixtures ====================

@pytest.fixture
def sample_chat_messages():
    """Provide sample chat messages for testing."""
    from lindormmemobase.models.blob import OpenAICompatibleMessage
    
    return [
        OpenAICompatibleMessage(role="user", content="Hello! I'm planning a trip to Japan."),
        OpenAICompatibleMessage(role="assistant", content="That sounds exciting! When are you planning to go?"),
        OpenAICompatibleMessage(role="user", content="Probably in spring, around March or April."),
        OpenAICompatibleMessage(role="assistant", content="Perfect timing for cherry blossoms! Do you have any specific cities in mind?"),
        OpenAICompatibleMessage(role="user", content="I'm thinking Tokyo, Kyoto, and maybe Osaka."),
    ]


@pytest.fixture
def sample_chat_blob(sample_chat_messages):
    """Provide a sample ChatBlob for testing."""
    from lindormmemobase.models.blob import ChatBlob, BlobType
    
    return ChatBlob(
        messages=sample_chat_messages,
        type=BlobType.chat,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_doc_blob():
    """Provide a sample DocBlob for testing."""
    from lindormmemobase.models.blob import DocBlob, BlobType
    
    return DocBlob(
        content="User enjoys hiking and outdoor activities. Prefers mountain trails over beach walks.",
        type=BlobType.doc,
        created_at=datetime.now()
    )


@pytest.fixture
def sample_profile_config(mock_config):
    """Provide a sample ProfileConfig for testing."""
    from lindormmemobase.models.profile_topic import ProfileConfig
    
    return ProfileConfig.load_from_config(mock_config)


# ==================== Mock Response Fixtures ====================

@pytest.fixture
def mock_llm_extract_response() -> str:
    """Mock LLM response for profile extraction."""
    return """
{
    "user_profile_topics": [
        {
            "topic": "travel",
            "sub_topic": "destinations",
            "profile": "User is planning a trip to Japan in spring (March/April). Interested in visiting Tokyo, Kyoto, and Osaka."
        },
        {
            "topic": "interests",
            "sub_topic": "cultural",
            "profile": "User is interested in experiencing cherry blossoms in Japan."
        }
    ]
}
"""


@pytest.fixture
def mock_llm_merge_response() -> str:
    """Mock LLM response for profile merging."""
    return """
{
    "merged_profile": "User is planning a trip to Japan in spring (March/April) to see cherry blossoms. Plans to visit Tokyo, Kyoto, and Osaka."
}
"""


@pytest.fixture
def mock_embedding_vector(integration_config):
    """Provide a mock embedding vector with correct dimension from config."""
    import numpy as np
    # Use embedding dimension from config (default 1024 for LindormAI)
    dim = integration_config.embedding_dim if hasattr(integration_config, 'embedding_dim') else 1536
    return np.random.rand(dim).tolist()


# ==================== Test Utilities ====================

@pytest.fixture
def test_user_id() -> str:
    """Provide a consistent test user ID."""
    return "test_user_001"


@pytest.fixture
def test_project_id() -> str:
    """Provide a consistent test project ID."""
    return "test_project"


@pytest.fixture
def temp_yaml_config(tmp_path: Path) -> Path:
    """Create a temporary YAML configuration file for testing."""
    config_file = tmp_path / "test_config.yaml"
    config_content = """
language: en
llm_api_key: test-yaml-key
llm_base_url: http://yaml-test-server
best_llm_model: gpt-4o-mini
embedding_provider: openai
embedding_dim: 1536
lindorm_table_host: localhost
lindorm_table_port: 33060
lindorm_table_username: yaml_user
lindorm_table_password: yaml_pass
lindorm_table_database: yaml_test_db
"""
    config_file.write_text(config_content)
    return config_file


# ==================== Assertion Helpers ====================

def assert_promise_ok(promise_result, msg: str = "Promise should be ok"):
    """Assert that a Promise result is ok."""
    assert promise_result.ok(), f"{msg}: {promise_result.msg()}"


def assert_promise_error(promise_result, msg: str = "Promise should have error"):
    """Assert that a Promise result has an error."""
    assert not promise_result.ok(), f"{msg}: Expected error but got success"


# Make assertion helpers available as fixtures
@pytest.fixture
def assert_ok():
    """Provide assert_promise_ok helper."""
    return assert_promise_ok


@pytest.fixture
def assert_error():
    """Provide assert_promise_error helper."""
    return assert_promise_error
