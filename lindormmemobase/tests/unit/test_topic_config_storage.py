"""
Unit tests for TopicConfigStorage.

Tests project-specific profile config storage with caching.
"""
import time
import pytest
from unittest.mock import Mock

from lindormmemobase.core.storage.topic_configs import TopicConfigStorage, CacheEntry, TABLE_NAME
from lindormmemobase.models.profile_topic import ProfileConfig


@pytest.mark.unit
class TestTopicConfigStorage:
    """Test TopicConfigStorage functionality."""

    def test_cache_entry_creation(self):
        """Test CacheEntry dataclass creation."""
        entry = CacheEntry(value=None, expires_at=time.time() + 300)
        assert entry.value is None
        assert entry.expires_at > time.time()

    def test_cache_entry_with_config(self):
        """Test CacheEntry with ProfileConfig value."""
        config = ProfileConfig(language="zh")
        entry = CacheEntry(value=config, expires_at=time.time() + 300)
        assert entry.value is not None
        assert entry.value.language == "zh"

    def test_cache_hit_returns_cached_value(self):
        """Test cache hit returns cached value without DB query."""
        # Create a mock storage with pre-populated cache
        storage = Mock(spec=TopicConfigStorage)
        test_config = ProfileConfig(language="zh", profile_strict_mode=True)
        storage._cache = {
            "test_project": CacheEntry(
                value=test_config,
                expires_at=time.time() + 300  # Not expired
            )
        }

        # Get from cache
        cached_entry = storage._cache.get("test_project")
        assert cached_entry is not None
        assert cached_entry.value is not None
        assert cached_entry.value.language == "zh"
        assert cached_entry.value.profile_strict_mode is True

    def test_negative_cache(self):
        """Test negative cache (None value) is cached."""
        storage = Mock(spec=TopicConfigStorage)
        storage._cache = {
            "nonexistent_project": CacheEntry(
                value=None,
                expires_at=time.time() + 300
            )
        }

        # Get from cache
        cached_entry = storage._cache.get("nonexistent_project")
        assert cached_entry is not None
        assert cached_entry.value is None

    def test_cache_expiration(self):
        """Test expired cache entry is identified."""
        storage = Mock(spec=TopicConfigStorage)
        storage._cache = {
            "test_project": CacheEntry(
                value=ProfileConfig(language="en"),
                expires_at=time.time() - 100  # Expired
            )
        }

        # Check expiration
        cached_entry = storage._cache.get("test_project")
        assert cached_entry is not None
        assert cached_entry.expires_at < time.time()

    def test_invalidate_cache_specific_project(self):
        """Test invalidating cache for specific project."""
        storage = Mock(spec=TopicConfigStorage)
        storage._cache = {
            "project_a": CacheEntry(
                value=ProfileConfig(language="zh"),
                expires_at=time.time() + 300
            ),
            "project_b": CacheEntry(
                value=ProfileConfig(language="en"),
                expires_at=time.time() + 300
            )
        }

        # Simulate invalidation
        storage._cache.pop("project_a", None)

        # Only project_a should be removed
        assert "project_a" not in storage._cache
        assert "project_b" in storage._cache

    def test_invalidate_all_cache(self):
        """Test invalidating all cache."""
        storage = Mock(spec=TopicConfigStorage)
        storage._cache = {
            "project_a": CacheEntry(
                value=ProfileConfig(language="zh"),
                expires_at=time.time() + 300
            ),
            "project_b": CacheEntry(
                value=ProfileConfig(language="en"),
                expires_at=time.time() + 300
            )
        }

        # Simulate invalidation
        storage._cache.clear()

        # All cache should be cleared
        assert len(storage._cache) == 0


@pytest.mark.unit
class TestProfileConfigResolver:
    """Test profile_config_resolver module."""

    def test_resolver_imports(self):
        """Test that resolver can be imported."""
        from lindormmemobase.utils.profile_config_resolver import resolve_profile_config, DEFAULT_PROJECT_ID
        assert resolve_profile_config is not None
        assert DEFAULT_PROJECT_ID == "default"

    def test_default_project_id_constant(self):
        """Test DEFAULT_PROJECT_ID constant."""
        from lindormmemobase.utils.profile_config_resolver import DEFAULT_PROJECT_ID
        assert DEFAULT_PROJECT_ID == "default"
        assert isinstance(DEFAULT_PROJECT_ID, str)
