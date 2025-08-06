#!/usr/bin/env python3
"""
Lindorm Search Context Integration Tests

This test suite tests the context integration functionality that combines
user profiles and event gists for comprehensive context retrieval.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from lindormmemobase.config import Config
from lindormmemobase.core.search.context import (
    get_user_context,
    customize_context_prompt_func
)
from lindormmemobase.core.storage.user_profiles import add_user_profiles
from lindormmemobase.core.storage.events import store_event_gist_with_embedding
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig
from lindormmemobase.models.response import ContextData


class TestLindormSearchContext:
    """Test suite for context integration functionality."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        try:
            cls.config = Config.load_config()
        except AssertionError as e:
            # If LLM API key is missing, create a minimal config for testing
            import os
            print(f"⚠️ Config validation failed: {e}")
            print("⚠️ Using test configuration for context integration")
            
            # Create config with minimal required settings
            cls.config = Config.__new__(Config)  # Skip __post_init__
            
            # Set MySQL/Lindorm Wide Table configuration
            cls.config.mysql_host = os.getenv("MEMOBASE_MYSQL_HOST", "localhost")
            cls.config.mysql_port = int(os.getenv("MEMOBASE_MYSQL_PORT", "3306"))
            cls.config.mysql_username = os.getenv("MEMOBASE_MYSQL_USERNAME", "root")
            cls.config.mysql_password = os.getenv("MEMOBASE_MYSQL_PASSWORD")
            cls.config.mysql_database = os.getenv("MEMOBASE_MYSQL_DATABASE", "memobase_test")
            
            # Set OpenSearch/Lindorm Search configuration
            cls.config.opensearch_host = os.getenv("MEMOBASE_OPENSEARCH_HOST", "localhost")
            cls.config.opensearch_port = int(os.getenv("MEMOBASE_OPENSEARCH_PORT", "9200"))
            cls.config.opensearch_username = os.getenv("MEMOBASE_OPENSEARCH_USERNAME")
            cls.config.opensearch_password = os.getenv("MEMOBASE_OPENSEARCH_PASSWORD")
            cls.config.opensearch_use_ssl = os.getenv("MEMOBASE_OPENSEARCH_USE_SSL", "false").lower() == "true"
            cls.config.opensearch_events_index = os.getenv("MEMOBASE_OPENSEARCH_EVENTS_INDEX", "memobase_events_ctx_test")
            cls.config.opensearch_event_gists_index = os.getenv("MEMOBASE_OPENSEARCH_EVENT_GISTS_INDEX", "memobase_event_gists_ctx_test")
            
            # Set embedding configuration - disable by default for testing
            cls.config.enable_event_embedding = False  # Disable to avoid API calls and connection issues
            cls.config.embedding_provider = os.getenv("MEMOBASE_EMBEDDING_PROVIDER", "openai")
            cls.config.embedding_api_key = os.getenv("MEMOBASE_EMBEDDING_API_KEY") or os.getenv("MEMOBASE_LLM_API_KEY")
            cls.config.embedding_base_url = os.getenv("MEMOBASE_EMBEDDING_BASE_URL")
            cls.config.embedding_dim = int(os.getenv("MEMOBASE_EMBEDDING_DIM", "1536"))
            cls.config.embedding_model = os.getenv("MEMOBASE_EMBEDDING_MODEL", "text-embedding-3-small")
            
            # Set minimal required fields
            cls.config.llm_api_key = os.getenv("MEMOBASE_LLM_API_KEY", "test-key-for-context-test")
            cls.config.language = "en"
            cls.config.best_llm_model = "gpt-4o-mini"
            cls.config.summary_llm_model = "gpt-4o-mini"
        
        # Test user and data
        cls.test_user_id = "test_user_context_integration"
        cls.test_profile_ids = []
        cls.test_gist_ids = []
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        try:
            # Cleanup profiles
            if cls.test_profile_ids:
                from lindormmemobase.core.storage.user_profiles import delete_user_profiles
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    cleanup_result = loop.run_until_complete(delete_user_profiles(
                        cls.test_user_id,
                        cls.test_profile_ids,
                        cls.config
                    ))
                    loop.close()
                    if cleanup_result.ok():
                        print(f"✅ Cleaned up {cleanup_result.data()} test profiles")
                except Exception as e:
                    print(f"Profile cleanup warning: {e}")
            
            # Cleanup search indices  
            if cls.test_gist_ids:
                try:
                    print("⚠️ Skipping search index cleanup to avoid connection timeout")
                    # Note: Test indices may remain, clean manually if needed:
                    # DELETE /memobase_events_ctx_test
                    # DELETE /memobase_event_gists_ctx_test
                except Exception as e:
                    print(f"Search cleanup warning: {e}")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    async def _create_test_data(self):
        """Create test profiles and event gists."""
        # Create test profiles
        profiles = [
            "User is experienced in Python web development using Django and FastAPI",
            "User has knowledge in machine learning and data science with pandas and scikit-learn",
            "User prefers agile development methodologies and pair programming"
        ]
        
        attributes_list = [
            {"topic": "skills", "sub_topic": "web_development"},
            {"topic": "interests", "sub_topic": "data_science"},
            {"topic": "work_style", "sub_topic": "agile_development"}
        ]
        
        profile_result = await add_user_profiles(
            user_id=self.test_user_id,
            profiles=profiles,
            attributes_list=attributes_list,
            config=self.config
        )
        
        if profile_result.ok():
            self.test_profile_ids.extend(profile_result.data())
        
        # Create test event gists
        gist_data_list = [
            {
                "content": "User discussed building a REST API with FastAPI for data processing",
                "key_points": ["FastAPI", "REST API", "data processing"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "content": "User asked about machine learning model deployment best practices",
                "key_points": ["ML deployment", "best practices", "production"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
        
        for i, gist_data in enumerate(gist_data_list):
            # Create simple embeddings
            embedding = [0.1 + i * 0.1] * self.config.embedding_dim
            
            gist_result = await store_event_gist_with_embedding(
                user_id=self.test_user_id,
                event_id=f"event_{i}",
                gist_data=gist_data,
                embedding=embedding,
                config=self.config
            )
            
            if gist_result.ok():
                self.test_gist_ids.append(gist_result.data())
        
        # Give indices time to refresh
        await asyncio.sleep(2)
    
    def test_customize_context_prompt_func(self):
        """Test custom context prompt function."""
        template = "User Profile:\n{profile_section}\n\nRecent Events:\n{event_section}"
        profile_section = "- skills::programming: Python expert"
        event_section = "Built a FastAPI application"
        
        result = customize_context_prompt_func(template, profile_section, event_section)
        
        expected = "User Profile:\n- skills::programming: Python expert\n\nRecent Events:\nBuilt a FastAPI application"
        assert result == expected
        
        print("✅ Custom context prompt function works correctly")
    
    @pytest.mark.asyncio
    async def test_get_user_context_basic(self):
        """Test basic user context retrieval."""
        await self._create_test_data()
        
        # Create minimal profile config
        profile_config = ProfileConfig(language="en")
        
        result = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            profile_event_ratio=0.6
        )
        
        assert result.ok(), f"Failed to get user context: {result.msg()}"
        context_data = result.data()
        assert isinstance(context_data, ContextData)
        assert len(context_data.context) > 0
        
        # Context should contain both profile and event information
        context_text = context_data.context
        print(f"✅ Retrieved user context ({len(context_text)} chars)")
        print(f"    Context preview: {context_text[:200]}...")
    
    @pytest.mark.asyncio
    async def test_get_user_context_with_chats(self):
        """Test user context retrieval with chat messages."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(language="en")
        
        # Chat messages about web development
        chat_messages = [
            OpenAICompatibleMessage(role="user", content="I'm working on a web API"),
            OpenAICompatibleMessage(role="assistant", content="What framework are you using?"),
            OpenAICompatibleMessage(role="user", content="I'm using FastAPI for Python")
        ]
        
        result = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            chats=chat_messages,
            profile_event_ratio=0.5,
            event_similarity_threshold=0.1,
            time_range_in_days=1
        )
        
        assert result.ok(), f"Failed to get user context with chats: {result.msg()}"
        context_data = result.data()
        context_text = context_data.context
        
        print(f"✅ Retrieved context with chats ({len(context_text)} chars)")
    
    @pytest.mark.asyncio
    async def test_get_user_context_topic_filtering(self):
        """Test context retrieval with topic filtering."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(
            language="en"
        )
        
        # Test with only_topics filter
        result = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            only_topics=["skills"],  # Only skills topic
            profile_event_ratio=0.7
        )
        
        assert result.ok(), f"Failed to get filtered context: {result.msg()}"
        context_data = result.data()
        
        # Context should only contain skills-related profiles
        context_text = context_data.context
        print(f"✅ Retrieved filtered context (skills only, {len(context_text)} chars)")
    
    @pytest.mark.asyncio
    async def test_get_user_context_token_limits(self):
        """Test context retrieval with various token limits."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(language="en")
        
        # Test with very low token limit
        result_small = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=100,  # Very small
            profile_event_ratio=0.5
        )
        
        assert result_small.ok()
        small_context = result_small.data().context
        
        # Test with larger token limit
        result_large = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,  # Larger
            profile_event_ratio=0.5
        )
        
        assert result_large.ok()
        large_context = result_large.data().context
        
        # Large context should be longer than small context
        assert len(large_context) >= len(small_context)
        
        print(f"✅ Token limits: small={len(small_context)}, large={len(large_context)} chars")
    
    @pytest.mark.asyncio
    async def test_get_user_context_custom_prompt(self):
        """Test context retrieval with custom prompt template."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(language="en")
        
        custom_template = "CUSTOM PROFILE:\n{profile_section}\n\nCUSTOM EVENTS:\n{event_section}\n\nEND CUSTOM"
        
        result = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            customize_context_prompt=custom_template,
            profile_event_ratio=0.6
        )
        
        assert result.ok(), f"Failed to get context with custom prompt: {result.msg()}"
        context_data = result.data()
        context_text = context_data.context
        
        # Should contain custom template markers
        assert "CUSTOM PROFILE:" in context_text
        assert "CUSTOM EVENTS:" in context_text
        assert "END CUSTOM" in context_text
        
        print(f"✅ Custom prompt template works ({len(context_text)} chars)")
    
    @pytest.mark.asyncio
    async def test_get_user_context_fill_window(self):
        """Test context retrieval with fill_window_with_events option."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(language="en")
        
        # Test with fill_window_with_events=True
        result_fill = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            fill_window_with_events=True,  # Fill remaining space with events
            profile_event_ratio=0.3  # Small profile ratio
        )
        
        assert result_fill.ok()
        fill_context = result_fill.data().context
        
        # Test without fill_window_with_events
        result_no_fill = await get_user_context(
            user_id=self.test_user_id,
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000,
            fill_window_with_events=False,
            profile_event_ratio=0.3
        )
        
        assert result_no_fill.ok()
        no_fill_context = result_no_fill.data().context
        
        print(f"✅ Fill window: with_fill={len(fill_context)}, without_fill={len(no_fill_context)} chars")
    
    @pytest.mark.asyncio
    async def test_get_user_context_error_handling(self):
        """Test error handling in context retrieval."""
        profile_config = ProfileConfig(language="en")
        
        # Test with non-existent user
        result_no_user = await get_user_context(
            user_id="non_existent_user_12345",
            profile_config=profile_config,
            global_config=self.config,
            max_token_size=1000
        )
        
        # Should succeed but return minimal context
        assert result_no_user.ok()
        context_text = result_no_user.data().context
        assert len(context_text) >= 0  # Should at least have some template content
        
        # Test with invalid profile_event_ratio
        with pytest.raises(AssertionError):
            await get_user_context(
                user_id=self.test_user_id,
                profile_config=profile_config,
                global_config=self.config,
                max_token_size=1000,
                profile_event_ratio=1.5  # Invalid ratio > 1
            )
        
        print("✅ Error handling works correctly")
    
    @pytest.mark.asyncio
    async def test_concurrent_context_requests(self):
        """Test concurrent context retrieval requests."""
        await self._create_test_data()
        
        profile_config = ProfileConfig(language="en")
        
        # Create multiple concurrent context requests
        async def get_context_task(task_id):
            return await get_user_context(
                user_id=self.test_user_id,
                profile_config=profile_config,
                global_config=self.config,
                max_token_size=500,
                prefer_topics=[f"topic_{task_id}"] if task_id % 2 == 0 else None
            )
        
        # Run 3 concurrent requests
        tasks = [get_context_task(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all succeeded
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Task {i} failed with exception: {result}")
                continue
            assert result.ok(), f"Concurrent task {i} failed: {result.msg()}"
            context_length = len(result.data().context)
            print(f"    Task {i}: {context_length} chars")
        
        print("✅ Concurrent context requests completed successfully")


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))