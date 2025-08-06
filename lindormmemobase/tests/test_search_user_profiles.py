#!/usr/bin/env python3
"""
Lindorm Search User Profiles Integration Tests

This test suite tests the user profile search and filtering functionality
using real configurations from .env and config.yaml.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from lindormmemobase.config import Config
from lindormmemobase.core.search.user_profiles import (
    truncate_profiles,
    get_user_profiles_data,
    filter_profiles_with_chats,
    try_json_reason
)
from lindormmemobase.core.storage.user_profiles import (
    add_user_profiles,
    get_lindorm_table_storage
)
from lindormmemobase.models.blob import OpenAICompatibleMessage
from lindormmemobase.models.response import UserProfilesData


class TestLindormSearchUserProfiles:
    """Test suite for user profile search functionality."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        try:
            cls.config = Config.load_config()
        except AssertionError as e:
            # If LLM API key is missing, create a minimal config for testing
            import os
            print(f"⚠️ Config validation failed: {e}")
            print("⚠️ Using test configuration (no real LLM API key required for most tests)")
            
            # Create config with minimal required settings
            cls.config = Config.__new__(Config)  # Skip __post_init__
            
            # Set MySQL/Lindorm configuration from environment or defaults
            cls.config.mysql_host = os.getenv("MEMOBASE_MYSQL_HOST", "localhost")
            cls.config.mysql_port = int(os.getenv("MEMOBASE_MYSQL_PORT", "3306"))
            cls.config.mysql_username = os.getenv("MEMOBASE_MYSQL_USERNAME", "root")
            cls.config.mysql_password = os.getenv("MEMOBASE_MYSQL_PASSWORD")
            cls.config.mysql_database = os.getenv("MEMOBASE_MYSQL_DATABASE", "memobase_test")
            
            # Set minimal required fields
            cls.config.llm_api_key = os.getenv("MEMOBASE_LLM_API_KEY", "test-key-for-profile-test")
            cls.config.language = "en"
            cls.config.best_llm_model = "gpt-4o-mini"
            cls.config.summary_llm_model = "gpt-4o-mini"
            cls.config.enable_event_embedding = False
            cls.config.max_profile_subtopics = 15
        
        # Test user and profile data
        cls.test_user_id = "test_user_profile_search"
        cls.test_profile_ids = []  # Keep track of created profiles for cleanup
        
    @classmethod
    def teardown_class(cls):
        """Clean up test data."""
        try:
            if cls.test_profile_ids:
                # Create a new event loop for cleanup if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        print(f"⚠️ Skipping cleanup due to running event loop")
                        return
                except RuntimeError:
                    pass
                
                from lindormmemobase.core.storage.user_profiles import delete_user_profiles
                cleanup_result = asyncio.run(delete_user_profiles(
                    cls.test_user_id, 
                    cls.test_profile_ids,
                    cls.config
                ))
                if cleanup_result.ok():
                    print(f"✅ Cleaned up {cleanup_result.data()} test profiles")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_connection(self):
        """Test basic connection to Lindorm Wide Table."""
        try:
            storage = get_lindorm_table_storage(self.config)
            pool = storage._get_pool()
            conn = pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            assert result[0] == 1
            print("✅ Connected to Lindorm Wide Table successfully")
        except Exception as e:
            pytest.fail(f"Failed to connect to Lindorm Wide Table: {e}")
    
    async def _create_test_profiles(self) -> List[str]:
        """Helper method to create test profiles."""
        profiles = [
            "User is proficient in Python programming and enjoys working on web applications",
            "User has experience with machine learning, specifically using TensorFlow and PyTorch",
            "User prefers working in collaborative team environments and values code reviews",
            "User is interested in data science and has knowledge of statistics and data analysis",
            "User works primarily on backend development using FastAPI and Django frameworks"
        ]
        
        attributes_list = [
            {"topic": "skills", "sub_topic": "programming"},
            {"topic": "interests", "sub_topic": "machine_learning"},
            {"topic": "work_style", "sub_topic": "collaboration"},
            {"topic": "interests", "sub_topic": "data_science"},
            {"topic": "skills", "sub_topic": "backend_development"}
        ]
        
        result = await add_user_profiles(
            user_id=self.test_user_id,
            profiles=profiles,
            attributes_list=attributes_list,
            config=self.config
        )
        
        assert result.ok(), f"Failed to create test profiles: {result.msg()}"
        profile_ids = result.data()
        self.test_profile_ids.extend(profile_ids)
        
        return profile_ids
    
    def test_try_json_reason(self):
        """Test JSON reason extraction utility."""
        # Test valid JSON with reason
        valid_content = 'Some text before {"reason": "Selected profiles based on user interests", "other": "data"} some text after'
        reason = try_json_reason(valid_content)
        assert reason == "Selected profiles based on user interests"
        
        # Test invalid JSON
        invalid_content = "This is not a valid JSON string"
        reason = try_json_reason(invalid_content)
        assert reason is None
        
        # Test JSON without reason
        no_reason_content = 'Text {"other_key": "value", "data": 123}'
        reason = try_json_reason(no_reason_content)
        assert reason is None
        
        print("✅ JSON reason extraction works correctly")
    
    @pytest.mark.asyncio
    async def test_truncate_profiles_basic(self):
        """Test basic profile truncation functionality."""
        # Create test profiles
        await self._create_test_profiles()
        
        # Get profiles from storage
        from lindormmemobase.core.storage.user_profiles import get_user_profiles
        result = await get_user_profiles(self.test_user_id, self.config)
        assert result.ok()
        profiles_data = result.data()
        
        # Test topk truncation
        truncated = await truncate_profiles(profiles_data, topk=3)
        assert truncated.ok()
        assert len(truncated.data().profiles) <= 3
        
        # Test token size truncation
        truncated_tokens = await truncate_profiles(profiles_data, max_token_size=100)
        assert truncated_tokens.ok()
        # Should have fewer profiles due to token limit
        assert len(truncated_tokens.data().profiles) <= len(profiles_data.profiles)
        
        print(f"✅ Profile truncation: {len(profiles_data.profiles)} → {len(truncated.data().profiles)} (topk), {len(truncated_tokens.data().profiles)} (tokens)")
    
    @pytest.mark.asyncio
    async def test_truncate_profiles_topic_filtering(self):
        """Test topic-based profile filtering and limiting."""
        await self._create_test_profiles()
        
        from lindormmemobase.core.storage.user_profiles import get_user_profiles
        result = await get_user_profiles(self.test_user_id, self.config)
        assert result.ok()
        profiles_data = result.data()
        
        # Test prefer_topics (should prioritize certain topics)
        preferred = await truncate_profiles(
            profiles_data, 
            prefer_topics=["interests", "skills"]
        )
        assert preferred.ok()
        # Check that preferred topics come first
        preferred_profiles = preferred.data().profiles
        if len(preferred_profiles) > 0:
            first_topic = preferred_profiles[0].attributes.get("topic")
            assert first_topic in ["interests", "skills"]
        
        # Test only_topics (should filter to only specified topics)
        skills_only = await truncate_profiles(
            profiles_data,
            only_topics=["skills"]
        )
        assert skills_only.ok()
        skills_profiles = skills_only.data().profiles
        for profile in skills_profiles:
            assert profile.attributes.get("topic") == "skills"
        
        # Test max_subtopic_size
        limited_subtopics = await truncate_profiles(
            profiles_data,
            max_subtopic_size=1
        )
        assert limited_subtopics.ok()
        
        print(f"✅ Topic filtering: all={len(profiles_data.profiles)}, skills_only={len(skills_profiles)}")
    
    @pytest.mark.asyncio
    async def test_get_user_profiles_data(self):
        """Test the main user profiles data retrieval function."""
        await self._create_test_profiles()
        
        # Test basic profile data retrieval
        result = await get_user_profiles_data(
            user_id=self.test_user_id,
            max_profile_token_size=500,
            prefer_topics=["skills"],
            only_topics=None,
            max_subtopic_size=None,
            topic_limits={},
            chats=[],  # No chats for basic test
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        assert result.ok(), f"Failed to get user profiles data: {result.msg()}"
        profile_section, use_profiles = result.data()
        
        assert isinstance(profile_section, str)
        assert isinstance(use_profiles, list)
        assert len(profile_section) > 0, "Profile section should not be empty"
        assert len(use_profiles) > 0, "Should have some profiles"
        
        # Verify profile section format
        assert profile_section.startswith("- "), "Profile section should start with bullet point"
        assert "::" in profile_section, "Profile section should contain topic::subtopic format"
        
        print(f"✅ Retrieved profiles data: {len(use_profiles)} profiles, {len(profile_section)} chars")
        
        # Print detailed profile results
        print(f"🔍 用户档案检索详细结果:")
        print(f"{'-'*60}")
        print(f"档案数量: {len(use_profiles)}")
        print(f"档案文本长度: {len(profile_section)} 字符")
        print(f"\n📝 档案文本内容预览:")
        preview_text = profile_section[:300] if len(profile_section) > 300 else profile_section
        print(preview_text)
        if len(profile_section) > 300:
            print(f"... (显示前300字符，总共{len(profile_section)}字符)")
        
        print(f"\n📋 档案对象详情（前5个）:")
        for i, profile in enumerate(use_profiles[:5]):
            print(f"  Profile {i+1}:")
            print(f"    ID: {profile.id}")
            print(f"    内容: {profile.content[:50]}{'...' if len(profile.content) > 50 else ''}")
            print(f"    主题: {profile.attributes.get('topic', '未知')} :: {profile.attributes.get('sub_topic', '未知')}")
            print(f"    更新时间: {profile.updated_at}")
            print()
        if len(use_profiles) > 5:
            print(f"... 还有 {len(use_profiles) - 5} 个档案")
        print(f"{'-'*60}")
        
    
    @pytest.mark.asyncio
    async def test_get_user_profiles_data_with_limits(self):
        """Test profile data retrieval with various limits."""
        await self._create_test_profiles()
        
        # Test with zero token limit (should return empty)
        result_empty = await get_user_profiles_data(
            user_id=self.test_user_id,
            max_profile_token_size=0,  # Zero tokens
            prefer_topics=[],
            only_topics=None,
            max_subtopic_size=None,
            topic_limits={},
            chats=[],
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        assert result_empty.ok()
        profile_section, use_profiles = result_empty.data()
        assert profile_section == "", "Profile section should be empty with zero token limit"
        assert len(use_profiles) == 0, "Should have no profiles with zero token limit"
        
        # Test with topic limits
        result_limited = await get_user_profiles_data(
            user_id=self.test_user_id,
            max_profile_token_size=1000,
            prefer_topics=[],
            only_topics=["skills", "interests"],
            max_subtopic_size=1,  # Limit subtopics
            topic_limits={"skills": 1, "interests": 1},  # Limit each topic
            chats=[],
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        assert result_limited.ok()
        profile_section_limited, use_profiles_limited = result_limited.data()
        
        print(f"✅ Profile limits: empty={len(use_profiles)}, limited={len(use_profiles_limited)}")
        
        # Print detailed limit results
        print(f"🔍 档案限制测试详细结果:")
        print(f"{'-'*60}")
        print(f"零限制结果: {len(use_profiles)} 个档案")
        print(f"有限制结果: {len(use_profiles_limited)} 个档案")
        
        if use_profiles_limited:
            print(f"\n📋 限制后的档案详情:")
            for i, profile in enumerate(use_profiles_limited):
                print(f"  Profile {i+1}:")
                print(f"    内容: {profile.content[:40]}{'...' if len(profile.content) > 40 else ''}")
                print(f"    主题: {profile.attributes.get('topic')} :: {profile.attributes.get('sub_topic')}")
        print(f"{'-'*60}")
        
    
    @pytest.mark.asyncio
    async def test_filter_profiles_with_chats(self):
        """Test filtering profiles based on chat context."""
        if not self.config.llm_api_key or self.config.llm_api_key == "test-key-for-profile-test":
            pytest.skip("Profile filtering with chats requires real LLM API key")
        
        await self._create_test_profiles()
        
        # Get all profiles
        from lindormmemobase.core.storage.user_profiles import get_user_profiles
        result = await get_user_profiles(self.test_user_id, self.config)
        assert result.ok()
        profiles_data = result.data()
        
        # Create chat messages about programming
        chat_messages = [
            OpenAICompatibleMessage(role="user", content="I'm working on a Python web application"),
            OpenAICompatibleMessage(role="assistant", content="That sounds interesting! What framework are you using?"),
            OpenAICompatibleMessage(role="user", content="I'm using FastAPI for the backend"),
            OpenAICompatibleMessage(role="assistant", content="Great choice! FastAPI is excellent for building APIs.")
        ]
        
        # Filter profiles based on chat context
        filter_result = await filter_profiles_with_chats(
            user_id=self.test_user_id,
            profiles=profiles_data,
            chats=chat_messages,
            global_config=self.config,
            only_topics=None,
            max_value_token_size=50,
            max_previous_chats=4,
            max_filter_num=3
        )
        
        assert filter_result.ok(), f"Failed to filter profiles: {filter_result.msg()}"
        filtered_data = filter_result.data()
        
        assert "reason" in filtered_data
        assert "profiles" in filtered_data
        assert isinstance(filtered_data["profiles"], list)
        
        # Should have selected relevant profiles based on Python/FastAPI context
        print(f"✅ Filtered {len(profiles_data.profiles)} → {len(filtered_data['profiles'])} profiles")
        print(f"    Reason: {filtered_data['reason']}")
        
        # Print detailed filtering results
        print(f"🔍 聊天上下文档案过滤详细结果:")
        print(f"{'-'*70}")
        print(f"原始档案数量: {len(profiles_data.profiles)}")
        print(f"过滤后档案数量: {len(filtered_data['profiles'])}")
        print(f"过滤原因: {filtered_data['reason']}")
        
        print(f"\n💬 聊天上下文:")
        for i, msg in enumerate(chat_messages):
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"  {i+1}. {msg.role}: {content_preview}")
        
        print(f"\n📋 被选中的相关档案:")
        for i, profile in enumerate(filtered_data['profiles']):
            print(f"  Profile {i+1}:")
            print(f"    内容: {profile.content[:60]}{'...' if len(profile.content) > 60 else ''}")
            print(f"    主题: {profile.attributes.get('topic')} :: {profile.attributes.get('sub_topic')}")
            print()
        print(f"{'-'*70}")
        
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for various edge cases."""
        # Test with non-existent user
        result_no_user = await get_user_profiles_data(
            user_id="non_existent_user_12345",
            max_profile_token_size=100,
            prefer_topics=[],
            only_topics=None,
            max_subtopic_size=None,
            topic_limits={},
            chats=[],
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        # Should succeed but return empty or minimal results
        assert result_no_user.ok()
        profile_section, use_profiles = result_no_user.data()
        assert profile_section.strip() in ["", "-"]  # May return empty or just "-" 
        assert len(use_profiles) == 0
        
        # Test filter_profiles_with_chats with empty data
        empty_profiles = UserProfilesData(profiles=[])
        empty_chats = []
        
        filter_result = await filter_profiles_with_chats(
            user_id=self.test_user_id,
            profiles=empty_profiles,
            chats=empty_chats,
            global_config=self.config
        )
        
        # Should fail gracefully
        assert not filter_result.ok()
        assert "No chats or profiles to filter" in filter_result.msg()
        
        print("✅ Error handling works correctly")
    
    @pytest.mark.asyncio
    async def test_concurrent_profile_operations(self):
        """Test concurrent profile operations."""
        # Create multiple batches of profiles concurrently
        async def create_profile_batch(batch_id):
            profiles = [f"Concurrent batch {batch_id} profile {i}" for i in range(2)]
            attributes = [{"topic": f"batch_{batch_id}", "sub_topic": f"item_{i}"} for i in range(2)]
            
            result = await add_user_profiles(
                user_id=f"{self.test_user_id}_concurrent_{batch_id}",
                profiles=profiles,
                attributes_list=attributes,
                config=self.config
            )
            return result
        
        # Run 3 concurrent batches
        tasks = [create_profile_batch(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        # Verify all succeeded
        for i, result in enumerate(results):
            assert result.ok(), f"Concurrent batch {i} failed: {result.msg()}"
            assert len(result.data()) == 2
        
        print("✅ Concurrent profile operations completed successfully")
        
        # Cleanup concurrent test data
        for i in range(3):
            from lindormmemobase.core.storage.user_profiles import delete_user_profiles
            cleanup_result = await delete_user_profiles(
                user_id=f"{self.test_user_id}_concurrent_{i}",
                profile_ids=results[i].data(),
                config=self.config
            )
            # Don't assert cleanup success to avoid test failure

    @pytest.mark.asyncio
    async def test_profile_search_demonstration(self):
        """专门用于展示档案搜索内容的测试函数"""
        print(f"\n🎯 档案搜索内容演示测试开始...")
        print(f"{'='*80}")
        
        # 创建更多样化的测试档案
        demo_profiles = [
            "用户精通Python和JavaScript编程，有5年的Web开发经验",
            "用户喜欢使用React和Vue.js开发前端应用，对用户体验设计很有兴趣", 
            "用户在机器学习领域有深入研究，熟悉TensorFlow和PyTorch框架",
            "用户偏好敏捷开发方法论，喜欢在小团队中协作工作",
            "用户有丰富的数据库设计经验，熟练使用MySQL和PostgreSQL",
            "用户对云计算技术很感兴趣，有AWS和Azure的实践经验",
            "用户喜欢阅读技术书籍，经常参加技术会议和研讨会",
            "用户有创业经历，曾经创办过一家技术初创公司"
        ]
        
        demo_attributes = [
            {"topic": "skills", "sub_topic": "programming"},
            {"topic": "skills", "sub_topic": "frontend"},
            {"topic": "interests", "sub_topic": "machine_learning"},
            {"topic": "work", "sub_topic": "methodology"},
            {"topic": "skills", "sub_topic": "database"},
            {"topic": "interests", "sub_topic": "cloud_computing"},
            {"topic": "life_event", "sub_topic": "learning"},
            {"topic": "work", "sub_topic": "entrepreneurship"}
        ]
        
        # 存储演示档案
        demo_user_id = f"{self.test_user_id}_demo"
        demo_profile_ids = []
        
        from lindormmemobase.core.storage.user_profiles import add_user_profiles
        result = await add_user_profiles(
            user_id=demo_user_id,
            profiles=demo_profiles,
            attributes_list=demo_attributes,
            config=self.config
        )
        
        if result.ok():
            demo_profile_ids = result.data()
            print(f"✅ 创建了 {len(demo_profile_ids)} 个演示档案")
        
        # 1. 基础档案检索演示
        print(f"\n🔍 基础档案检索演示:")
        print(f"{'-'*60}")
        
        basic_result = await get_user_profiles_data(
            user_id=demo_user_id,
            max_profile_token_size=2000,
            prefer_topics=["skills", "interests"],
            only_topics=None,
            max_subtopic_size=3,
            topic_limits={"skills": 2, "interests": 2},
            chats=[],
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        if basic_result.ok():
            profile_section, profiles = basic_result.data()
            print(f"📋 检索结果: {len(profiles)} 个档案")
            print(f"📝 档案文本长度: {len(profile_section)} 字符")
            print(f"\n档案文本内容:")
            print(profile_section)
            
            print(f"\n📋 档案对象详情:")
            for i, profile in enumerate(profiles):
                print(f"  {i+1}. [{profile.attributes.get('topic')}::{profile.attributes.get('sub_topic')}]")
                print(f"     {profile.content}")
                print()
        
        # 2. 主题过滤演示
        print(f"\n🎯 主题过滤演示:")
        print(f"{'-'*60}")
        
        topic_filter_result = await get_user_profiles_data(
            user_id=demo_user_id,
            max_profile_token_size=1500,
            prefer_topics=["skills"],
            only_topics=["skills", "interests"],  # 只要技能和兴趣
            max_subtopic_size=2,
            topic_limits={},
            chats=[],
            full_profile_and_only_search_event=False,
            global_config=self.config
        )
        
        if topic_filter_result.ok():
            filtered_section, filtered_profiles = topic_filter_result.data()
            print(f"📊 过滤后结果: {len(filtered_profiles)} 个档案 (只显示skills和interests)")
            
            # 统计主题分布
            topic_counts = {}
            for profile in filtered_profiles:
                topic = profile.attributes.get('topic', 'unknown')
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            print(f"主题分布: {topic_counts}")
            
            for i, profile in enumerate(filtered_profiles):
                print(f"  {i+1}. [{profile.attributes.get('topic')}::{profile.attributes.get('sub_topic')}]")
                print(f"     {profile.content[:50]}{'...' if len(profile.content) > 50 else ''}")
        
        # 3. 聊天上下文过滤演示
        if self.config.llm_api_key and self.config.llm_api_key != "test-key-for-profile-test":
            print(f"\n💬 聊天上下文过滤演示:")
            print(f"{'-'*60}")
            
            # 获取所有档案
            from lindormmemobase.core.storage.user_profiles import get_user_profiles
            all_profiles_result = await get_user_profiles(demo_user_id, self.config)
            if all_profiles_result.ok():
                all_profiles_data = all_profiles_result.data()
                
                # 创建关于云计算的聊天上下文
                cloud_chat = [
                    OpenAICompatibleMessage(role="user", content="我想学习云计算技术"),
                    OpenAICompatibleMessage(role="assistant", content="那很棒！你对哪个云平台更感兴趣？"),
                    OpenAICompatibleMessage(role="user", content="我听说AWS和Azure都不错，你觉得呢？")
                ]
                
                filter_result = await filter_profiles_with_chats(
                    user_id=demo_user_id,
                    profiles=all_profiles_data,
                    chats=cloud_chat,
                    global_config=self.config,
                    only_topics=None,
                    max_filter_num=3
                )
                
                if filter_result.ok():
                    filtered_data = filter_result.data()
                    print(f"🤖 AI过滤结果: {len(all_profiles_data.profiles)} → {len(filtered_data['profiles'])} 个档案")
                    print(f"🧠 过滤原因: {filtered_data['reason']}")
                    
                    print(f"\n被选中的相关档案:")
                    for i, profile in enumerate(filtered_data['profiles']):
                        print(f"  {i+1}. [{profile.attributes.get('topic')}::{profile.attributes.get('sub_topic')}]")
                        print(f"     {profile.content}")
                        print()
        else:
            print(f"\n⚠️  聊天上下文过滤演示跳过（需要真实的LLM API密钥）")
        
        # 清理演示数据
        if demo_profile_ids:
            from lindormmemobase.core.storage.user_profiles import delete_user_profiles
            cleanup_result = await delete_user_profiles(demo_user_id, demo_profile_ids, self.config)
            if cleanup_result.ok():
                print(f"\n✅ 清理了 {cleanup_result.data()} 个演示档案")
        
        print(f"{'='*80}")
        print(f"✅ 档案搜索内容演示测试完成!")


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s", "--tb=short"]))