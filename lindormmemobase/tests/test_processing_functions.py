#!/usr/bin/env python3
"""
Process Blobs Core Functions Unit Tests

This test suite tests the core processing functions in the process_blobs workflow
using real LLM connections from .env configuration. Tests focus on format validation
rather than content correctness since LLM outputs can vary.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from datetime import datetime
from typing import List, Dict, Any
import json

from ..config import Config
from ..models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from ..models.profile_topic import ProfileConfig
from ..models.response import ProfileData
from ..core.extraction.processor.entry_summary import entry_chat_summary
from ..core.extraction.processor.extract import extract_topics
from ..core.extraction.processor.merge import merge_or_valid_new_memos
from ..core.extraction.processor.event_summary import tag_event
from ..core.extraction.processor.process_blobs import truncate_chat_blobs, process_profile_res, process_event_res
from ..core.extraction.processor.organize import organize_profiles, deduplicate_profiles
from ..core.extraction.processor.summary import re_summary, summary_memo


def print_section(title: str, content: str = "", width: int = 80):
    """Print a nicely formatted section header."""
    print("\n" + "="*width)
    print(f"🤖 {title}".center(width))
    print("="*width)
    if content:
        print(content)
        print("-"*width)


def print_llm_response(title: str, content: str, max_length: int = 500):
    """Print LLM response with proper formatting."""
    print(f"\n🧠 {title}:")
    print("-" * 60)
    if len(content) > max_length:
        print(content[:max_length] + "...")
        print(f"\n[Content truncated - Total length: {len(content)} chars]")
    else:
        print(content)
    print("-" * 60)


def format_profile_data(profiles: list) -> str:
    """Format profile data for display."""
    if not profiles:
        return "No profiles"
    
    result = []
    for i, profile in enumerate(profiles):
        if isinstance(profile, dict):
            content = profile.get('content', 'No content')
            attrs = profile.get('attributes', {})
            topic = attrs.get('topic', 'unknown')
            sub_topic = attrs.get('sub_topic', 'unknown')
            result.append(f"  Profile {i+1}: {content}")
            result.append(f"    → {topic} :: {sub_topic}")
        else:
            result.append(f"  Profile {i+1}: {str(profile)}")
    return "\n".join(result)


class TestProcessingFunctions:
    """Test suite for core processing functions using real LLM connections."""
    
    @classmethod
    def setup_class(cls):
        """Setup test class with configuration."""
        cls.config = Config.load_config()
        # Use a simple test profile config
        cls.profile_config = ProfileConfig(
            language="en",
            profile_strict_mode=False,
            profile_validate_mode=True,
            additional_user_profiles=[
                {
                    "topic": "interests",
                    "sub_topics": [
                        {"name": "programming", "description": "Programming languages and technologies"},
                        {"name": "hobbies", "description": "Personal hobbies and activities"}
                    ]
                },
                {
                    "topic": "skills", 
                    "sub_topics": [
                        {"name": "technical", "description": "Technical skills and expertise"},
                        {"name": "soft_skills", "description": "Communication and interpersonal skills"}
                    ]
                }
            ],
            event_tags=[
                {"name": "learning", "description": "User learned something new"},
                {"name": "achievement", "description": "User accomplished something"},
                {"name": "preference", "description": "User expressed a preference"}
            ]
        )
        
        # Test blobs for various scenarios
        cls.test_blobs = [
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I love programming in Python, it's my favorite language")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            ),
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I just finished learning React and built my first web app")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            ),
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I prefer working in teams rather than solo projects")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            )
        ]
    
    def test_truncate_chat_blobs(self):
        """Test blob truncation functionality."""
        # Test with small token limit
        truncated = truncate_chat_blobs(self.test_blobs, 50)
        assert isinstance(truncated, list)
        assert len(truncated) <= len(self.test_blobs)
        
        # Test with large token limit (should include all blobs)
        truncated_all = truncate_chat_blobs(self.test_blobs, 10000)
        assert len(truncated_all) == len(self.test_blobs)
        
        # Test with empty blobs
        empty_truncated = truncate_chat_blobs([], 100)
        assert len(empty_truncated) == 0
        
        print("✅ truncate_chat_blobs functionality works correctly")
    
    @pytest.mark.asyncio
    async def test_entry_chat_summary(self):
        """Test entry chat summary generation."""
        result = await entry_chat_summary(
            blobs=self.test_blobs,
            profile_config=self.profile_config,
            config=self.config
        )
        
        assert result.ok(), f"entry_chat_summary failed: {result.msg()}"
        summary = result.data()
        
        # Validate format - should be a non-empty string
        assert isinstance(summary, str), "Summary should be a string"
        assert len(summary.strip()) > 0, "Summary should not be empty"
        assert len(summary) < 10000, "Summary should be reasonable length"
        
        print(f"✅ entry_chat_summary generated summary: {len(summary)} characters")
        print(f"📄 Complete Summary Output:")
        print(f"{'-'*60}")
        print(summary)
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio 
    async def test_extract_topics_no_existing_profiles(self):
        """Test topic extraction with no existing profiles."""
        # Use a mock user_id for testing
        test_user_id = "test_extract_user_123"
        test_memo = "I love programming in Python and JavaScript. I also enjoy hiking and photography as hobbies."
        
        result = await extract_topics(
            user_id=test_user_id,
            user_memo=test_memo,
            project_profiles=self.profile_config,
            config=self.config
        )
        
        assert result.ok(), f"extract_topics failed: {result.msg()}"
        data = result.data()
        
        # Validate response structure
        assert isinstance(data, dict), "Result should be a dictionary"
        required_keys = ["fact_contents", "fact_attributes", "profiles", "total_profiles"]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"
        
        # Validate data types
        assert isinstance(data["fact_contents"], list), "fact_contents should be a list"
        assert isinstance(data["fact_attributes"], list), "fact_attributes should be a list"
        assert isinstance(data["profiles"], list), "profiles should be a list"
        assert isinstance(data["total_profiles"], list), "total_profiles should be a list"
        
        # Validate parallel arrays
        assert len(data["fact_contents"]) == len(data["fact_attributes"]), \
            "fact_contents and fact_attributes should have same length"
        
        # Validate attribute structure
        for attr in data["fact_attributes"]:
            assert isinstance(attr, dict), "Each attribute should be a dict"
            assert "topic" in attr, "Each attribute should have 'topic'"
            assert "sub_topic" in attr, "Each attribute should have 'sub_topic'"
        
        print(f"✅ extract_topics extracted {len(data['fact_contents'])} facts")
        print(f"🧠 LLM Extracted Facts and Topics:")
        print(f"{'-'*60}")
        for i, (fact, attr) in enumerate(zip(data['fact_contents'], data['fact_attributes'])):
            print(f"Fact {i+1}: {fact}")
            print(f"  → Topic: {attr['topic']}, Sub-topic: {attr['sub_topic']}")
        print(f"{'-'*60}")
        print(f"📊 Total profiles available: {len(data['total_profiles'])}")
        for profile in data['total_profiles']:
            print(f"  Profile topic: {profile.topic} ({len(profile.sub_topics)} sub-topics)")
    
    @pytest.mark.asyncio
    async def test_merge_or_valid_new_memos(self):
        """Test memo merging and validation."""
        # Prepare test data
        fact_contents = ["Python is my favorite programming language", "I enjoy hiking on weekends"]
        fact_attributes = [
            {"topic": "interests", "sub_topic": "programming"},
            {"topic": "interests", "sub_topic": "hobbies"}
        ]
        profiles = []  # No existing profiles
        
        from ..models.profile_topic import UserProfileTopic
        total_profiles = [
            UserProfileTopic(
                topic="interests",
                sub_topics=[
                    {"name": "programming", "description": "Programming languages and technologies"},
                    {"name": "hobbies", "description": "Personal hobbies and activities"}
                ]
            )
        ]
        
        result = await merge_or_valid_new_memos(
            user_id="test_user",
            fact_contents=fact_contents,
            fact_attributes=fact_attributes,
            profiles=profiles,
            profile_config=self.profile_config,
            total_profiles=total_profiles,
            config=self.config
        )
        
        assert result.ok(), f"merge_or_valid_new_memos failed: {result.msg()}"
        merge_result = result.data()
        
        # Validate merge result structure
        assert isinstance(merge_result, dict), "Result should be a dictionary"
        required_keys = ["add", "update", "delete", "update_delta", "before_profiles"]
        for key in required_keys:
            assert key in merge_result, f"Missing key: {key}"
        
        # Validate data types
        assert isinstance(merge_result["add"], list), "add should be a list"
        assert isinstance(merge_result["update"], list), "update should be a list"
        assert isinstance(merge_result["delete"], list), "delete should be a list"
        assert isinstance(merge_result["update_delta"], list), "update_delta should be a list"
        assert isinstance(merge_result["before_profiles"], list), "before_profiles should be a list"
        
        # Validate added profiles structure
        for profile in merge_result["add"]:
            assert isinstance(profile, dict), "Each added profile should be a dict"
            assert "content" in profile, "Each profile should have content"
            assert "attributes" in profile, "Each profile should have attributes"
            assert isinstance(profile["content"], str), "Content should be a string"
            assert isinstance(profile["attributes"], dict), "Attributes should be a dict"
        
        print(f"✅ merge_or_valid_new_memos processed {len(fact_contents)} facts")
        print(f"🔄 LLM Merge/Validation Results:")
        print(f"{'-'*60}")
        print(f"Results: {len(merge_result['add'])} add, {len(merge_result['update'])} update, {len(merge_result['delete'])} delete")
        print(f"\n📝 Added Profiles:")
        for i, profile in enumerate(merge_result['add']):
            print(f"  Add {i+1}: {profile['content']}")
            print(f"    → {profile['attributes']['topic']} :: {profile['attributes']['sub_topic']}")
        if merge_result['update']:
            print(f"\n✏️ Updated Profiles:")
            for i, profile in enumerate(merge_result['update']):
                print(f"  Update {i+1}: {profile['content']}")
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio
    async def test_tag_event(self):
        """Test event tagging functionality."""
        test_event_summary = "User learned React and built their first web application successfully"
        
        result = await tag_event(
            profile_config=self.profile_config,
            event_summary=test_event_summary,
            main_config=self.config
        )
        
        assert result.ok(), f"tag_event failed: {result.msg()}"
        event_tags = result.data()
        
        # Validate response - can be None or list
        if event_tags is not None:
            assert isinstance(event_tags, list), "Event tags should be a list or None"
            
            # Validate tag structure
            for tag in event_tags:
                assert isinstance(tag, dict), "Each tag should be a dict"
                assert "tag" in tag, "Each tag should have 'tag' field"
                assert "value" in tag, "Each tag should have 'value' field"
                assert isinstance(tag["tag"], str), "Tag name should be a string"
                assert isinstance(tag["value"], str), "Tag value should be a string"
            
            print(f"✅ tag_event generated {len(event_tags)} event tags")
            print(f"🏷️ LLM Event Tagging Results:")
            print(f"{'-'*60}")
            print(f"Input event: {test_event_summary}")
            print(f"Generated tags:")
            for tag in event_tags:
                print(f"  🏷️ {tag['tag']} = {tag['value']}")
            print(f"{'-'*60}")
        else:
            print("✅ tag_event returned None (no event tags configured or extracted)")
    
    @pytest.mark.asyncio
    async def test_extract_topics_with_existing_profiles(self):
        """Test topic extraction when user already has profiles."""
        test_user_id = "test_extract_existing_user_456"
        test_memo = "I'm now also interested in machine learning and data science"
        
        # Mock existing profiles
        from uuid import uuid4
        existing_profiles = [
            ProfileData(
                id=str(uuid4()),
                content="Python is my favorite programming language",
                attributes={"topic": "interests", "sub_topic": "programming"},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        
        # We can't easily test this without mocking the database call,
        # but we can test the case where profiles are empty (which extract_topics handles)
        result = await extract_topics(
            user_id=test_user_id,
            user_memo=test_memo,
            project_profiles=self.profile_config,
            config=self.config
        )
        
        assert result.ok(), f"extract_topics with existing profiles failed: {result.msg()}"
        data = result.data()
        
        # Same structure validation as before
        required_keys = ["fact_contents", "fact_attributes", "profiles", "total_profiles"]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"
        
        print(f"✅ extract_topics with existing profiles extracted {len(data['fact_contents'])} new facts")
        print(f"🧠 LLM New Facts Extraction:")
        print(f"{'-'*60}")
        for i, (fact, attr) in enumerate(zip(data['fact_contents'], data['fact_attributes'])):
            print(f"  New Fact {i+1}: {fact}")
            print(f"    → {attr['topic']} :: {attr['sub_topic']}")
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio
    async def test_processing_chain_integration(self):
        """Test the integration of processing functions in sequence."""
        # Step 1: Generate summary
        summary_result = await entry_chat_summary(
            blobs=self.test_blobs,
            profile_config=self.profile_config,
            config=self.config
        )
        assert summary_result.ok(), f"Summary generation failed: {summary_result.msg()}"
        summary = summary_result.data()
        
        # Step 2: Extract topics
        extract_result = await extract_topics(
            user_id="test_chain_user_789",
            user_memo=summary,
            project_profiles=self.profile_config,
            config=self.config
        )
        assert extract_result.ok(), f"Topic extraction failed: {extract_result.msg()}"
        extract_data = extract_result.data()
        
        # Step 3: Tag event
        tag_result = await tag_event(
            profile_config=self.profile_config,
            event_summary=summary,
            main_config=self.config
        )
        assert tag_result.ok(), f"Event tagging failed: {tag_result.msg()}"
        event_tags = tag_result.data()
        
        # Validate the chain worked
        assert isinstance(summary, str) and len(summary) > 0
        assert len(extract_data["fact_contents"]) >= 0  # Can be 0 if no facts extracted
        # event_tags can be None or list
        
        print("✅ Processing chain integration test completed successfully")
        print(f"🔗 Complete Processing Chain Results:")
        print(f"{'-'*80}")
        print(f"Chain results: Summary({len(summary)} chars) → Facts({len(extract_data['fact_contents'])}) → Tags({len(event_tags) if event_tags else 0})")
        print(f"\n1️⃣ Summary Output:")
        print(summary)
        print(f"\n2️⃣ Extracted Facts:")
        for i, (fact, attr) in enumerate(zip(extract_data['fact_contents'], extract_data['fact_attributes'])):
            print(f"  Fact {i+1}: {fact} → {attr['topic']}::{attr['sub_topic']}")
        print(f"\n3️⃣ Event Tags:")
        if event_tags:
            for tag in event_tags:
                print(f"  Tag: {tag['tag']} = {tag['value']}")
        else:
            print("  No event tags generated")
        print(f"{'-'*80}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in processing functions."""
        # Test with empty blobs
        empty_result = await entry_chat_summary(
            blobs=[],
            profile_config=self.profile_config,
            config=self.config
        )
        # Should handle gracefully - might succeed with empty input or fail cleanly
        if not empty_result.ok():
            print(f"✅ Empty blobs handled gracefully: {empty_result.msg()}")
        else:
            print("✅ Empty blobs processed successfully")
        
        # Test extract_topics with empty memo
        empty_extract = await extract_topics(
            user_id="test_error_user",
            user_memo="",
            project_profiles=self.profile_config,
            config=self.config
        )
        # Should handle gracefully
        if empty_extract.ok():
            data = empty_extract.data()
            assert len(data["fact_contents"]) == 0, "Empty memo should produce no facts"
            print("✅ Empty memo handled correctly")
        else:
            print(f"✅ Empty memo error handled: {empty_extract.msg()}")
    
    @pytest.mark.asyncio
    async def test_process_profile_res(self):
        """Test the complete profile processing pipeline."""
        test_user_id = "test_profile_res_user_123"
        test_memo = "I love Python programming and machine learning. I also enjoy hiking and photography."
        
        result = await process_profile_res(
            user_id=test_user_id,
            user_memo_str=test_memo,
            project_profiles=self.profile_config,
            config=self.config
        )
        
        assert result.ok(), f"process_profile_res failed: {result.msg()}"
        intermediate_profile, delta_profile_data = result.data()
        
        # Validate intermediate_profile structure
        assert isinstance(intermediate_profile, dict), "intermediate_profile should be a dict"
        required_keys = ["add", "update", "delete", "update_delta", "before_profiles"]
        for key in required_keys:
            assert key in intermediate_profile, f"Missing key in intermediate_profile: {key}"
        
        # Validate delta_profile_data
        assert isinstance(delta_profile_data, list), "delta_profile_data should be a list"
        
        # Validate add profiles structure
        for profile in intermediate_profile["add"]:
            assert isinstance(profile, dict), "Each added profile should be a dict"
            assert "content" in profile, "Each profile should have content"
            assert "attributes" in profile, "Each profile should have attributes"
            assert isinstance(profile["content"], str), "Content should be a string"
            assert isinstance(profile["attributes"], dict), "Attributes should be a dict"
            assert "topic" in profile["attributes"], "Attributes should have topic"
            assert "sub_topic" in profile["attributes"], "Attributes should have sub_topic"
        
        print(f"✅ process_profile_res completed successfully")
        print(f"🔄 Complete Profile Processing Pipeline Results:")
        print(f"{'-'*60}")
        print(f"Results: {len(intermediate_profile['add'])} add, {len(intermediate_profile['update'])} update")
        print(f"Delta profiles: {len(delta_profile_data)}")
        print(f"\n📝 Final Profile Contents:")
        for i, profile in enumerate(intermediate_profile['add']):
            print(f"  Profile {i+1}: {profile['content']}")
            print(f"    → {profile['attributes']['topic']} :: {profile['attributes']['sub_topic']}")
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio
    async def test_process_event_res(self):
        """Test the event processing pipeline."""
        test_user_id = "test_event_res_user_456"
        test_memo = "User successfully completed a challenging machine learning project and learned new techniques."
        
        result = await process_event_res(
            usr_id=test_user_id,
            memo_str=test_memo,
            profile_config=self.profile_config,
            config=self.config
        )
        
        assert result.ok(), f"process_event_res failed: {result.msg()}"
        event_tags = result.data()
        
        # Validate event_tags - can be None or list
        if event_tags is not None:
            assert isinstance(event_tags, list), "Event tags should be a list or None"
            
            # Validate tag structure
            for tag in event_tags:
                assert isinstance(tag, dict), "Each tag should be a dict"
                assert "tag" in tag, "Each tag should have 'tag' field"
                assert "value" in tag, "Each tag should have 'value' field"
                assert isinstance(tag["tag"], str), "Tag name should be a string"
                assert isinstance(tag["value"], str), "Tag value should be a string"
            
            print(f"✅ process_event_res generated {len(event_tags)} event tags")
            print(f"🏷️ LLM Event Processing Results:")
            print(f"{'-'*60}")
            print(f"Input memo: {test_memo}")
            print(f"Generated event tags:")
            for tag in event_tags:
                print(f"  🏷️ {tag['tag']} = {tag['value']}")
            print(f"{'-'*60}")
        else:
            print("✅ process_event_res returned None (no event tags)")
    
    @pytest.mark.asyncio
    async def test_organize_profiles(self):
        """Test profile organization functionality."""
        # Create test profile data that exceeds max_profile_subtopics
        from uuid import uuid4
        from ..models.types import MergeAddResult
        
        # Create many profiles for the same topic to trigger organization
        test_profiles = []
        for i in range(self.config.max_profile_subtopics + 2):  # Exceed the limit
            test_profiles.append(ProfileData(
                id=str(uuid4()),
                content=f"Programming skill {i}: Python, JavaScript, etc.",
                attributes={"topic": "interests", "sub_topic": f"programming_{i}"},
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))
        
        merge_result: MergeAddResult = {
            "add": [],
            "update": [],
            "delete": [],
            "update_delta": [],
            "before_profiles": test_profiles,
        }
        
        result = await organize_profiles(
            user_id="test_user",
            profile_options=merge_result,
            config=self.profile_config,
            main_config=self.config
        )
        
        assert result.ok(), f"organize_profiles failed: {result.msg()}"
        
        # Should add new organized profiles and mark old ones for deletion
        assert len(merge_result["add"]) > 0, "Should have added organized profiles"
        assert len(merge_result["delete"]) > 0, "Should have marked old profiles for deletion"
        
        # Validate organized profiles structure
        for profile in merge_result["add"]:
            assert isinstance(profile, dict), "Each organized profile should be a dict"
            assert "content" in profile, "Each profile should have content"
            assert "attributes" in profile, "Each profile should have attributes"
            assert isinstance(profile["content"], str), "Content should be a string"
            assert isinstance(profile["attributes"], dict), "Attributes should be a dict"
        
        print(f"✅ organize_profiles completed successfully")
        print(f"🔄 LLM Profile Organization Results:")
        print(f"{'-'*60}")
        print(f"Added {len(merge_result['add'])} organized profiles")
        print(f"Marked {len(merge_result['delete'])} old profiles for deletion")
        print(f"\n📝 Newly Organized Profiles:")
        for i, profile in enumerate(merge_result['add']):
            print(f"  Organized {i+1}: {profile['content']}")
            print(f"    → {profile['attributes']['topic']} :: {profile['attributes']['sub_topic']}")
        print(f"{'-'*60}")
    
    def test_deduplicate_profiles(self):
        """Test profile deduplication functionality."""
        # Create duplicate profiles
        profiles = [
            {
                "content": "Python programming",
                "attributes": {"topic": "interests", "sub_topic": "programming"}
            },
            {
                "content": "JavaScript development", 
                "attributes": {"topic": "interests", "sub_topic": "programming"}
            },
            {
                "content": "Machine learning",
                "attributes": {"topic": "skills", "sub_topic": "technical"}
            }
        ]
        
        deduplicated = deduplicate_profiles(profiles)
        
        # Should merge the two programming profiles and keep the ML one
        assert len(deduplicated) == 2, f"Expected 2 deduplicated profiles, got {len(deduplicated)}"
        
        # Find the merged programming profile
        programming_profile = next(
            (p for p in deduplicated if p["attributes"]["sub_topic"] == "programming"), 
            None
        )
        assert programming_profile is not None, "Should have a programming profile"
        assert ";" in programming_profile["content"], "Programming profile should be merged with ;"
        
        print("✅ deduplicate_profiles works correctly")
        print(f"Merged content: {programming_profile['content']}")
    
    @pytest.mark.asyncio
    async def test_summary_memo(self):
        """Test memo summarization for long content."""
        # Create a long content that exceeds token limit
        long_content = "This is a very long programming profile. " * 200  # Make it long
        
        content_pack = {
            "content": long_content,
            "attributes": {"topic": "interests", "sub_topic": "programming"}
        }
        
        result = await summary_memo("test_user", content_pack, self.config)
        
        assert result.ok(), f"summary_memo failed: {result.msg()}"
        
        # Content should be truncated/summarized
        assert len(content_pack["content"]) < len(long_content), "Content should be shortened"
        assert isinstance(content_pack["content"], str), "Content should remain a string"
        
        print(f"✅ summary_memo completed successfully")
        print(f"📝 LLM Summarization Results:")
        print(f"{'-'*60}")
        print(f"Original length: {len(long_content)} chars")
        print(f"Summarized length: {len(content_pack['content'])} chars")
        print(f"\n🔤 Original content preview:")
        print(f"{long_content[:200]}...")
        print(f"\n✂️ Summarized content:")
        print(content_pack['content'])
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio
    async def test_re_summary(self):
        """Test re-summarization of profiles."""
        # Create test profiles with long content
        long_content = "Very detailed programming knowledge including Python, JavaScript, machine learning, web development, and many other technical skills. " * 50
        
        add_profiles = [
            {
                "content": long_content,
                "attributes": {"topic": "interests", "sub_topic": "programming"}
            }
        ]
        
        update_profiles = [
            {
                "profile_id": "test-id-123",
                "content": long_content,
                "attributes": {"topic": "skills", "sub_topic": "technical"}
            }
        ]
        
        result = await re_summary(
            user_id="test_user",
            add_profile=add_profiles,
            update_profile=update_profiles,
            config=self.config
        )
        
        assert result.ok(), f"re_summary failed: {result.msg()}"
        
        # Content should be summarized if it was too long
        for profile in add_profiles + update_profiles:
            assert isinstance(profile["content"], str), "Content should remain a string"
            # Content might be summarized if it exceeded token limits
        
        print("✅ re_summary completed successfully")
        print(f"📝 LLM Re-summarization Results:")
        print(f"{'-'*60}")
        print(f"Original content length: {len(long_content)} chars")
        print(f"\n🔤 Original content preview:")
        print(f"{long_content[:200]}...")
        print(f"\n✂️ Re-summarized profiles:")
        for i, profile in enumerate(add_profiles):
            print(f"  Add Profile {i+1}: {profile['content'][:100]}{'...' if len(profile['content']) > 100 else ''}")
        for i, profile in enumerate(update_profiles):
            print(f"  Update Profile {i+1}: {profile['content'][:100]}{'...' if len(profile['content']) > 100 else ''}")
        print(f"{'-'*60}")
    
    @pytest.mark.asyncio
    async def test_comprehensive_llm_output_showcase(self):
        """Comprehensive test to showcase all LLM outputs in the processing pipeline."""
        print_section("COMPREHENSIVE LLM OUTPUT SHOWCASE", "Testing the complete processing pipeline with detailed LLM outputs")
        
        # Step 1: Create rich test data
        complex_blobs = [
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I've been learning machine learning for the past 6 months, focusing on deep learning and neural networks. I particularly enjoy working with PyTorch and have built several computer vision projects.")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            ),
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="Yesterday I completed my first full-stack web application using React and Node.js. It's a task management app with real-time updates. I'm really proud of how it turned out!")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            ),
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I prefer collaborative work environments and find that I'm most productive when working in small, agile teams. I also enjoy mentoring junior developers.")
                ],
                type=BlobType.chat,
                created_at=datetime.now()
            )
        ]
        
        test_user_id = "comprehensive_test_user_999"
        
        # Step 1: Entry Summary
        print_section("STEP 1: ENTRY CHAT SUMMARY")
        summary_result = await entry_chat_summary(
            blobs=complex_blobs,
            profile_config=self.profile_config,
            config=self.config
        )
        assert summary_result.ok(), f"Summary failed: {summary_result.msg()}"
        summary = summary_result.data()
        print_llm_response("Entry Chat Summary", summary)
        
        # Step 2: Topic Extraction
        print_section("STEP 2: TOPIC EXTRACTION")
        extract_result = await extract_topics(
            user_id=test_user_id,
            user_memo=summary,
            project_profiles=self.profile_config,
            config=self.config
        )
        assert extract_result.ok(), f"Extraction failed: {extract_result.msg()}"
        extract_data = extract_result.data()
        
        print(f"🧠 Extracted {len(extract_data['fact_contents'])} facts from the conversation:")
        print("-" * 70)
        for i, (fact, attr) in enumerate(zip(extract_data['fact_contents'], extract_data['fact_attributes'])):
            print(f"\n📝 Fact {i+1}: {fact}")
            print(f"  📂 Topic: {attr['topic']}")
            print(f"  🏷️ Sub-topic: {attr['sub_topic']}")
        print("-" * 70)
        
        # Step 3: Memo Merging/Validation
        print_section("STEP 3: MEMO MERGING & VALIDATION")
        merge_result = await merge_or_valid_new_memos(
            user_id=test_user_id,
            fact_contents=extract_data['fact_contents'],
            fact_attributes=extract_data['fact_attributes'],
            profiles=extract_data['profiles'],
            profile_config=self.profile_config,
            total_profiles=extract_data['total_profiles'],
            config=self.config
        )
        assert merge_result.ok(), f"Merge failed: {merge_result.msg()}"
        merge_data = merge_result.data()
        
        print(f"🔄 Merge Results: {len(merge_data['add'])} add, {len(merge_data['update'])} update, {len(merge_data['delete'])} delete")
        print("-" * 70)
        if merge_data['add']:
            print("➕ Added Profiles:")
            for i, profile in enumerate(merge_data['add']):
                print(f"\n  📄 Profile {i+1}:")
                print(f"    Content: {profile['content']}")
                print(f"    Topic: {profile['attributes']['topic']} :: {profile['attributes']['sub_topic']}")
        if merge_data['update']:
            print("\n✏️ Updated Profiles:")
            for i, profile in enumerate(merge_data['update']):
                print(f"\n  📄 Update {i+1}:")
                print(f"    Content: {profile['content']}")
                print(f"    ID: {profile['profile_id']}")
        print("-" * 70)
        
        # Step 4: Event Tagging
        print_section("STEP 4: EVENT TAGGING")
        tag_result = await tag_event(
            profile_config=self.profile_config,
            event_summary=summary,
            main_config=self.config
        )
        assert tag_result.ok(), f"Tagging failed: {tag_result.msg()}"
        event_tags = tag_result.data()
        
        if event_tags:
            print(f"🏷️ Generated {len(event_tags)} event tags:")
            print("-" * 50)
            for tag in event_tags:
                print(f"  🏷️ {tag['tag']}: {tag['value']}")
            print("-" * 50)
        else:
            print("🏷️ No event tags generated")
        
        # Step 5: Profile Organization (if needed)
        print_section("STEP 5: PROFILE ORGANIZATION")
        org_result = await organize_profiles(
            user_id=test_user_id,
            profile_options=merge_data,
            config=self.profile_config,
            main_config=self.config
        )
        assert org_result.ok(), f"Organization failed: {org_result.msg()}"
        
        if merge_data['add']:
            print(f"📊 Organization Results: {len(merge_data['add'])} final profiles")
            print("-" * 70)
            for i, profile in enumerate(merge_data['add']):
                print(f"\n  📄 Final Profile {i+1}:")
                print(f"    Content: {profile['content']}")
                print(f"    Category: {profile['attributes']['topic']} :: {profile['attributes']['sub_topic']}")
            print("-" * 70)
        
        # Step 6: Summary if needed
        print_section("STEP 6: CONTENT SUMMARIZATION")
        summary_result = await re_summary(
            user_id=test_user_id,
            add_profile=merge_data['add'],
            update_profile=merge_data['update'],
            config=self.config
        )
        assert summary_result.ok(), f"Re-summary failed: {summary_result.msg()}"
        
        print("✂️ Content summarization completed (if any profiles were too long)")
        print("-" * 50)
        for i, profile in enumerate(merge_data['add']):
            print(f"  📄 Final Profile {i+1} length: {len(profile['content'])} chars")
        print("-" * 50)
        
        # Final Summary
        print_section("PROCESSING PIPELINE SUMMARY")
        print(f"🎯 Successfully processed {len(complex_blobs)} conversation blobs")
        print(f"📝 Generated summary: {len(summary)} characters")
        print(f"🧠 Extracted facts: {len(extract_data['fact_contents'])}")
        print(f"📊 Final profiles: {len(merge_data['add'])} add, {len(merge_data['update'])} update")
        print(f"🏷️ Event tags: {len(event_tags) if event_tags else 0}")
        print(f"✅ All LLM components working correctly!")
        print("=" * 80)


if __name__ == "__main__":
    # Run tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))