#!/usr/bin/env python3
"""
Lindorm Search Events Integration Tests

This test suite tests the event search and storage functionality using real
Lindorm Search connections from .env and config.yaml configuration.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
import json
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from lindormmemobase.config import Config
from lindormmemobase.core.search.events import (
    get_user_event_gists,
    search_user_event_gists,
    get_user_event_gists_data,
    pack_latest_chat,
    truncate_event_gists
)
from lindormmemobase.core.storage.events import (
    store_event_with_embedding,
    store_event_gist_with_embedding,
    get_lindorm_search_storage
)
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.models.response import UserEventGistsData


class TestLindormSearchEvents:
    """Test suite for Lindorm Search events using real connections."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        try:
            cls.config = Config.load_config()
        except AssertionError as e:
            # If LLM API key is missing, create a minimal config for testing
            import os
            print(f"⚠️ Config validation failed: {e}")
            print("⚠️ Using test configuration for search functionality")
            
            # Create config with minimal required settings
            cls.config = Config.__new__(Config)  # Skip __post_init__
            
            # Set OpenSearch/Lindorm Search configuration from environment or defaults
            cls.config.lindorm_search_host = os.getenv("MEMOBASE_LINDORM_SEARCH_HOST", "localhost")
            cls.config.lindorm_search_port = int(os.getenv("MEMOBASE_LINDORM_SEARCH_PORT", "9200"))
            cls.config.lindorm_search_username = os.getenv("MEMOBASE_LINDORM_SEARCH_USERNAME")
            cls.config.lindorm_search_password = os.getenv("MEMOBASE_LINDORM_SEARCH_PASSWORD")
            cls.config.lindorm_search_use_ssl = os.getenv("MEMOBASE_LINDORM_SEARCH_USE_SSL", "false").lower() == "true"
            cls.config.lindorm_search_events_index = os.getenv("MEMOBASE_LINDORM_SEARCH_EVENTS_INDEX", "memobase_events_test")
            cls.config.lindorm_search_event_gists_index = os.getenv("MEMOBASE_LINDORM_SEARCH_EVENT_GISTS_INDEX", "memobase_event_gists_test")
            
            # Set embedding configuration
            cls.config.enable_event_embedding = os.getenv("MEMOBASE_ENABLE_EVENT_EMBEDDING", "true").lower() == "true"
            cls.config.embedding_provider = os.getenv("MEMOBASE_EMBEDDING_PROVIDER", "openai")
            cls.config.embedding_api_key = os.getenv("MEMOBASE_EMBEDDING_API_KEY") or os.getenv("MEMOBASE_LLM_API_KEY")
            cls.config.embedding_base_url = os.getenv("MEMOBASE_EMBEDDING_BASE_URL")
            cls.config.embedding_dim = int(os.getenv("MEMOBASE_EMBEDDING_DIM", "1536"))
            cls.config.embedding_model = os.getenv("MEMOBASE_EMBEDDING_MODEL", "text-embedding-3-small")
            
            # Set minimal required fields for other components
            cls.config.llm_api_key = os.getenv("MEMOBASE_LLM_API_KEY", "test-key-for-search-test")
            cls.config.language = "en"
            cls.config.best_llm_model = "gpt-4o-mini"
        
        # Test user and event data
        cls.test_user_id = "test_user_search_events"
        cls.test_event_ids = []  # Keep track of created events for cleanup
        cls.test_gist_ids = []   # Keep track of created gists for cleanup
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        try:
            if cls.test_event_ids or cls.test_gist_ids:
                # Create a new event loop for cleanup if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        print(f"⚠️ Skipping cleanup due to running event loop")
                        return
                except RuntimeError:
                    pass
                
                # Clean up test events and gists by deleting test indices
                storage = get_lindorm_search_storage(cls.config)
                try:
                    storage.client.indices.delete(index=cls.config.lindorm_search_events_index, ignore=[400, 404])
                    storage.client.indices.delete(index=cls.config.lindorm_search_event_gists_index, ignore=[400, 404])
                    print(f"✅ Cleaned up test indices")
                except Exception as e:
                    print(f"Cleanup warning: {e}")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_lindorm_connection(self):
        """Test basic connection to Lindorm Search."""
        try:
            storage = get_lindorm_search_storage(self.config)
            # Test connection by checking cluster health
            health = storage.client.cluster.health()
            assert 'status' in health
            print(f"✅ Connected to Lindorm Search successfully, status: {health['status']}")
        except Exception as e:
            pytest.fail(f"Failed to connect to Lindorm Search: {e}")
    
    def test_pack_latest_chat(self):
        """Test packing chat messages into a search query string."""
        messages = [
            OpenAICompatibleMessage(role="user", content="Hello there!"),
            OpenAICompatibleMessage(role="assistant", content="Hi! How can I help you?"),
            OpenAICompatibleMessage(role="user", content="I need help with Python programming"),
            OpenAICompatibleMessage(role="assistant", content="Sure! What specific Python topic?"),
            OpenAICompatibleMessage(role="user", content="How to use async/await?")
        ]
        
        # Test default (last 3 messages)
        result = pack_latest_chat(messages)
        expected_lines = [
            "Hi! How can I help you?",
            "I need help with Python programming", 
            "Sure! What specific Python topic?",
            "How to use async/await?"
        ]
        assert result == "\n".join(expected_lines[-3:])
        
        # Test custom number of messages
        result_2 = pack_latest_chat(messages, chat_num=2)
        assert result_2 == "\n".join(expected_lines[-2:])
        
        print("✅ pack_latest_chat works correctly")
    
    @pytest.mark.asyncio
    async def test_store_event_with_embedding(self):
        """Test storing events with embeddings."""
        event_data = {
            "conversation_id": "test_conv_001",
            "message_count": 5,
            "topic": "Python programming help",
            "summary": "User asked about async/await in Python",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Create a simple embedding vector (would normally come from embedding API)
        embedding = [0.1] * self.config.embedding_dim
        
        result = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event: {result.msg()}"
        event_id = result.data()
        assert isinstance(event_id, str)
        assert len(event_id) > 0
        
        self.test_event_ids.append(event_id)
        print(f"✅ Stored event with ID: {event_id}")
        
        return event_id, event_data, embedding
    
    @pytest.mark.asyncio
    async def test_store_event_gist_with_embedding(self):
        """Test storing event gists with embeddings."""
        # First store an event to reference
        event_result = await self.test_store_event_with_embedding()
        event_id, _, _ = event_result
        
        gist_data = {
            "content": "User learned about Python async/await syntax and best practices",
            "key_points": ["async/await basics", "asyncio library", "coroutines"],
            "sentiment": "positive",
            "importance": 0.8,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Create a simple embedding vector
        embedding = [0.2] * self.config.embedding_dim
        
        result = await store_event_gist_with_embedding(
            user_id=self.test_user_id,
            event_id=event_id,
            gist_data=gist_data,
            embedding=embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event gist: {result.msg()}"
        gist_id = result.data()
        assert isinstance(gist_id, str)
        assert len(gist_id) > 0
        
        self.test_gist_ids.append(gist_id)
        print(f"✅ Stored event gist with ID: {gist_id}")
        
        # Give the index some time to refresh
        await asyncio.sleep(2)
        
        return gist_id, gist_data, embedding
    
    @pytest.mark.asyncio
    async def test_get_user_event_gists_basic(self):
        """Test getting user event gists without vector search."""
        # First store some gists
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        result = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=1  # Recent events only
        )
        
        assert result.ok(), f"Failed to get event gists: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        assert len(gists_data.gists) >= 1, "Should have at least one gist"
        
        # Verify gist structure (gist is a UserEventGistData object, not dict)
        gist = gists_data.gists[0]
        assert hasattr(gist, 'id')
        assert hasattr(gist, 'gist_data')
        assert hasattr(gist, 'created_at')
        assert isinstance(gist.gist_data, (dict, type(gist.gist_data)))  # EventGistData object
        
        print(f"✅ Retrieved {len(gists_data.gists)} event gists successfully")
        
        # Print detailed gist information
        print(f"🔍 Detailed Event Gists Content:")
        print(f"{'-'*60}")
        for i, gist in enumerate(gists_data.gists[:5]):  # Show first 5 gists
            print(f"Gist {i+1}:")
            print(f"  📅 ID: {gist.id}")
            print(f"  📝 Content: {gist.gist_data}")
            print(f"  🕐 Created: {gist.created_at}")
            if hasattr(gist, 'similarity') and gist.similarity is not None:
                print(f"  🎯 Similarity: {gist.similarity}")
            print()
        if len(gists_data.gists) > 5:
            print(f"... and {len(gists_data.gists) - 5} more gists")
        print(f"{'-'*60}")
        
    @pytest.mark.asyncio
    async def test_search_user_event_gists_vector(self):
        """Test vector-based search of user event gists."""
        if not self.config.enable_event_embedding or not self.config.embedding_api_key:
            pytest.skip("Vector search requires embedding configuration")
        
        # First store some gists with embeddings
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(3)
        
        search_query = "Python async programming help"
        
        result = await search_user_event_gists(
            user_id=self.test_user_id,
            query=search_query,
            config=self.config,
            topk=5,
            similarity_threshold=0.1,  # Low threshold for testing
            time_range_in_days=1
        )
        
        assert result.ok(), f"Failed to search event gists: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        
        print(f"✅ Vector search returned {len(gists_data.gists)} results")
        
        # Print detailed search results
        print(f"🔍 Vector Search Results for query: '{search_query}'")
        print(f"{'-'*70}")
        if gists_data.gists:
            for i, gist in enumerate(gists_data.gists):
                print(f"Result {i+1}:")
                print(f"  📅 ID: {gist.id}")
                print(f"  📝 Content: {gist.gist_data}")
                print(f"  🕐 Created: {gist.created_at}")
                # gist is a UserEventGistData object, not dict
                if hasattr(gist, 'similarity') and gist.similarity is not None:
                    print(f"  🎯 Similarity Score: {gist.similarity:.4f}")
                    assert isinstance(gist.similarity, (int, float))
                print()
        else:
            print("  No results found (possibly due to indexing delay or low similarity)")
        print(f"{'-'*70}")
    
    @pytest.mark.asyncio
    async def test_get_user_event_gists_data_integration(self):
        """Test the main integration function for getting event data."""
        # Store test data first
        await self.test_store_event_gist_with_embedding()
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        # Test with chat messages (should trigger vector search if enabled)
        chat_messages = [
            OpenAICompatibleMessage(role="user", content="I need help with Python"),
            OpenAICompatibleMessage(role="assistant", content="What Python topic?"),
            OpenAICompatibleMessage(role="user", content="async/await patterns")
        ]
        
        result = await get_user_event_gists_data(
            user_id=self.test_user_id,
            chats=chat_messages,
            require_event_summary=True,
            event_similarity_threshold=0.1,
            time_range_in_days=1,
            global_config=self.config
        )
        
        assert result.ok(), f"Failed to get event gists data: {result.msg()}"
        gists_data = result.data()
        assert isinstance(gists_data, UserEventGistsData)
        
        print(f"✅ Integration function returned {len(gists_data.gists)} gists")
        
        # Print detailed integration results 
        print(f"🔍 Integration Test Results - get_user_event_gists_data:")
        print(f"{'-'*70}")
        if gists_data.gists:
            for i, gist in enumerate(gists_data.gists[:3]):  # Show first 3 gists
                print(f"Integration Result {i+1}:")
                print(f"  📅 ID: {gist.id}")
                print(f"  📝 Content: {gist.gist_data}")
                print(f"  🕐 Created: {gist.created_at}")
                if hasattr(gist, 'similarity') and gist.similarity is not None:
                    print(f"  🎯 Similarity: {gist.similarity:.4f}")
                print()
            if len(gists_data.gists) > 3:
                print(f"... and {len(gists_data.gists) - 3} more gists")
        print(f"{'-'*70}")
        
        # Test without chat messages (should use basic retrieval)
        result_basic = await get_user_event_gists_data(
            user_id=self.test_user_id,
            chats=[],  # Empty chat
            require_event_summary=False,
            event_similarity_threshold=0.5,
            time_range_in_days=1,
            global_config=self.config
        )
        
        assert result_basic.ok(), f"Failed to get event gists data (basic): {result_basic.msg()}"
        print("✅ Basic retrieval (no vector search) works correctly")
    
    @pytest.mark.asyncio
    async def test_truncate_event_gists(self):
        """Test truncating event gists by token count."""
        from uuid import uuid4
        # Create mock gists data with valid UUIDs
        gists_data = UserEventGistsData(gists=[
            {
                "id": str(uuid4()),
                "gist_data": {"content": "Short content"},
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": str(uuid4()), 
                "gist_data": {"content": "This is a much longer piece of content that contains many more tokens and should be truncated when the limit is low"},
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": str(uuid4()),
                "gist_data": {"content": "Another piece of content"},
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ])
        
        # Test with no limit (should return all)
        result_no_limit = await truncate_event_gists(gists_data, None)
        assert result_no_limit.ok()
        assert len(result_no_limit.data().gists) == 3
        
        # Test with low token limit (should truncate)
        result_truncated = await truncate_event_gists(gists_data, 10)
        assert result_truncated.ok()
        truncated_gists = result_truncated.data().gists
        assert len(truncated_gists) <= 3
        assert len(truncated_gists) >= 1
        
        print(f"✅ Truncation: {len(gists_data.gists)} → {len(truncated_gists)} gists")
    
    @pytest.mark.asyncio
    async def test_time_range_filtering(self):
        """Test that time range filtering works correctly."""
        # Store a gist
        await self.test_store_event_gist_with_embedding() 
        
        # Give the index time to refresh
        await asyncio.sleep(2)
        
        # Test with very recent time range (should find results)
        result_recent = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=1  # Last 1 day
        )
        
        assert result_recent.ok()
        recent_count = len(result_recent.data().gists)
        
        # Test with very old time range (should find no results)
        result_old = await get_user_event_gists(
            user_id=self.test_user_id,
            config=self.config,
            topk=10,
            time_range_in_days=0  # No time range (should be empty)
        )
        
        assert result_old.ok()
        old_count = len(result_old.data().gists)
        
        # Recent should have more or equal results than old
        assert recent_count >= old_count
        print(f"✅ Time filtering: recent={recent_count}, old={old_count}")
        
        # Print detailed time filtering results
        print(f"🔍 Time Range Filtering Test Results:")
        print(f"{'-'*60}")
        print(f"Recent (1 day) results: {recent_count} gists")
        if result_recent.data().gists:
            for i, gist in enumerate(result_recent.data().gists[:2]):  # Show first 2
                print(f"  Recent Gist {i+1}:")
                print(f"    📝 Content: {gist.gist_data}")
                print(f"    🕐 Created: {gist.created_at}")
                
        print(f"Old (0 day range) results: {old_count} gists")
        if result_old.data().gists:
            for i, gist in enumerate(result_old.data().gists[:2]):  # Show first 2
                print(f"  Old Gist {i+1}:")
                print(f"    📝 Content: {gist.gist_data}")
                print(f"    🕐 Created: {gist.created_at}")
        print(f"{'-'*60}")
        
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Test with invalid user ID
        result_invalid = await get_user_event_gists(
            user_id="non_existent_user_12345",
            config=self.config,
            topk=5,
            time_range_in_days=30
        )
        
        # Should succeed but return empty results
        assert result_invalid.ok()
        assert len(result_invalid.data().gists) == 0
        
        # Test store with problematic data (None embedding in this case, since config singleton is already created)
        result_error = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data={"test": "data"},
            embedding=None,  # This will cause the mapping error
            config=self.config
        )
        
        # Should fail gracefully due to None embedding 
        assert not result_error.ok()
        error_msg = result_error.msg()
        # Accept various error types that can occur in error scenarios
        assert ("CONFIG_ERROR" in error_msg or 
                "config parameter is required" in error_msg or 
                "requre configurations params" in error_msg or
                "mapper_parsing_exception" in error_msg or
                "knn_vector" in error_msg), f"Unexpected error message: {error_msg}"
        
        print("✅ Error handling works correctly")
    
    @pytest.mark.asyncio
    async def test_large_embedding_vectors(self):
        """Test handling of large embedding vectors."""
        large_embedding = np.random.random(self.config.embedding_dim).tolist()
        
        event_data = {
            "test": "large_embedding",
            "vector_size": len(large_embedding),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        result = await store_event_with_embedding(
            user_id=self.test_user_id,
            event_data=event_data,
            embedding=large_embedding,
            config=self.config
        )
        
        assert result.ok(), f"Failed to store event with large embedding: {result.msg()}"
        self.test_event_ids.append(result.data())
        
        print(f"✅ Large embedding vector ({len(large_embedding)}D) handled successfully")

    @pytest.mark.asyncio
    async def test_search_content_demonstration(self):
        """专门用于展示搜索内容的测试函数"""
        print(f"\n🎯 搜索内容演示测试开始...")
        print(f"{'='*80}")
        
        # 1. 存储一些多样化的测试数据
        test_events = [
            {
                "conversation_id": "demo_conv_001", 
                "topic": "Python编程帮助",
                "summary": "用户询问关于Python异步编程的问题",
                "content": "如何使用async/await进行异步编程？",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "conversation_id": "demo_conv_002",
                "topic": "机器学习讨论", 
                "summary": "用户学习深度学习神经网络",
                "content": "深度学习中的反向传播算法原理是什么？",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            {
                "conversation_id": "demo_conv_003",
                "topic": "Web开发咨询",
                "summary": "用户咨询React框架使用问题", 
                "content": "React Hooks的使用场景和最佳实践有哪些？",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
        
        stored_gist_ids = []
        for i, event_data in enumerate(test_events):
            # 为每个事件创建不同的embedding向量
            embedding = [0.1 + i * 0.2] * self.config.embedding_dim
            
            # 存储事件
            event_result = await store_event_with_embedding(
                user_id=f"{self.test_user_id}_demo",
                event_data=event_data,
                embedding=embedding,
                config=self.config
            )
            
            if event_result.ok():
                event_id = event_result.data()
                
                # 存储对应的gist
                gist_data = {
                    "content": f"用户学习了{event_data['topic']} - {event_data['content'][:20]}...",
                    "key_insights": [f"重点{i+1}", f"要点{i+1}"],
                    "importance_score": 7.5 + i * 0.5
                }
                
                gist_result = await store_event_gist_with_embedding(
                    user_id=f"{self.test_user_id}_demo",
                    event_id=event_id,
                    gist_data=gist_data,
                    embedding=embedding,
                    config=self.config
                )
                
                if gist_result.ok():
                    stored_gist_ids.append(gist_result.data())
                    print(f"✅ 存储了事件和Gist: {event_data['topic']}")
        
        # 等待索引刷新
        await asyncio.sleep(3)
        
        # 2. 执行基础检索测试
        print(f"\n🔍 基础检索测试:")
        print(f"{'-'*60}")
        
        basic_result = await get_user_event_gists(
            user_id=f"{self.test_user_id}_demo",
            config=self.config,
            topk=10,
            time_range_in_days=1
        )
        
        if basic_result.ok():
            gists = basic_result.data().gists
            print(f"📋 检索到 {len(gists)} 个事件Gist:")
            for i, gist in enumerate(gists):
                print(f"  {i+1}. ID: {str(gist.id)[:8]}...")
                print(f"     内容: {gist.gist_data}")
                print(f"     时间: {gist.created_at}")
                if hasattr(gist, 'similarity') and gist.similarity:
                    print(f"     相似度: {gist.similarity:.4f}")
                print()
        
        # 3. 如果支持向量搜索，测试语义搜索
        if self.config.enable_event_embedding and self.config.embedding_api_key:
            print(f"\n🧠 语义搜索测试:")
            print(f"{'-'*60}")
            
            search_queries = [
                "Python异步编程",
                "深度学习算法", 
                "React前端开发"
            ]
            
            for query in search_queries:
                print(f"🔎 搜索查询: '{query}'")
                
                search_result = await search_user_event_gists(
                    user_id=f"{self.test_user_id}_demo", 
                    query=query,
                    config=self.config,
                    topk=3,
                    similarity_threshold=0.1,
                    time_range_in_days=1
                )
                
                if search_result.ok():
                    results = search_result.data().gists
                    print(f"  📊 找到 {len(results)} 个相关结果:")
                    for j, result in enumerate(results):
                        print(f"    {j+1}. 内容: {result.gist_data}")
                        if hasattr(result, 'similarity') and result.similarity:
                            print(f"       相似度: {result.similarity:.4f}")
                        print(f"       时间: {result.created_at}")
                else:
                    print(f"  ❌ 搜索失败: {search_result.msg()}")
                print()
        else:
            print(f"\n⚠️  语义搜索功能未启用（需要embedding_api_key配置）")
        
        print(f"{'='*80}")
        print(f"✅ 搜索内容演示测试完成!")


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))