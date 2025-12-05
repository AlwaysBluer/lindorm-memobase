#!/usr/bin/env python3
"""
LindormMemobase API Usage Demo

This script demonstrates how to use the LindormMemobase API for memory extraction,
profile management, and search functionality. It covers all major API methods
with practical examples.

Configuration:
- Before running this demo, ensure you have a proper config.yaml file
- Or set environment variables for API keys (MEMOBASE_LLM_API_KEY)
"""

import asyncio
import os
from pathlib import Path

from lindormmemobase import Config
from lindormmemobase.main import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, DocBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig


async def initialize_memobase():
    """
    Demonstrates different ways to initialize LindormMemobase
    """
    print("=== Initializing LindormMemobase ===")
    
    # Method 1: Use default configuration (loads from config files or environment)
    try:
        memobase = LindormMemobase()
        print("✓ Initialized with default configuration")
    except Exception as e:
        print(f"✗ Failed to initialize with default config: {e}")
        memobase = None

    # Method 2: From YAML file path
    config_path = "config.yaml"
    if Path(config_path).exists():
        try:
            config = Config.load_config(config_path)
            memobase = LindormMemobase(config)
            print("✓ Initialized from YAML file")
        except Exception as e:
            print(f"✗ Failed to initialize from YAML: {e}")
    else:
        print(f"⚠ Config file {config_path} not found, skipping this method")

    # For this demo, we'll create one with basic parameters
    print("config_path:", config_path)
    config = Config.load_config(config_path)
    memobase = LindormMemobase(config)
    print("✓ Initialized from YAML file")
    print("✓ Created demo memobase instance\n")
    return memobase


async def demo_memory_extraction(memobase):
    """
    Demonstrates memory extraction from user blobs
    """
    print("=== Memory Extraction Demo ===")
    
    # Create sample chat blobs
    chat_blob = ChatBlob(
        messages=[
            OpenAICompatibleMessage(role="user", content="I love hiking in the mountains on weekends"),
            OpenAICompatibleMessage(role="assistant", content="That sounds like a great hobby! What trails do you prefer?"),
            OpenAICompatibleMessage(role="user", content="I prefer trails with scenic views and waterfalls")
        ],
        type=BlobType.chat,
        created_at=None
    )

    blobs = [chat_blob]
    user_id = "demo_user_123"
    
    try:
        # Extract memories from blobs
        result = await memobase.extract_memories(
            user_id=user_id,
            blobs=blobs
        )
        print(f"✓ Memory extraction successful")
        print(f"  Result: {result}")
    except Exception as e:
        print(f"✗ Memory extraction failed: {e}")
    
    print()


async def demo_profile_management(memobase):
    """
    Demonstrates user profile retrieval and management
    """
    print("=== Profile Management Demo ===")
    
    user_id = "demo_user_123"
    
    try:
        # Get all user profiles
        profiles = await memobase.get_user_profiles(user_id)
        print(f"✓ Retrieved {len(profiles)} profile(s)")
        
        for profile in profiles:
            print(f"  Topic: {profile.topic}")
            for subtopic_name, entry in profile.subtopics.items():
                print(f"    - {subtopic_name}: {entry.content[:100]}...")
    except Exception as e:
        print(f"✗ Profile retrieval failed: {e}")
    
    # Get specific topics only
    try:
        specific_profiles = await memobase.get_user_profiles(
            user_id=user_id,
            topics=["interests", "preferences", "general"]
        )
        print(f"✓ Retrieved {len(specific_profiles)} profile(s) for specific topics")
    except Exception as e:
        print(f"✗ Specific topic retrieval failed: {e}")
    
    print()


async def demo_event_management(memobase):
    """
    Demonstrates event retrieval and search
    """
    print("=== Event Management Demo ===")
    
    user_id = "demo_user_123"
    try:
        # Search for specific events
        search_events = await memobase.search_events(
            user_id=user_id,
            query="hiking outdoor activities",
        )
        print(f"✓ Found {len(search_events)} matching events")
        
        for i, event in enumerate(search_events):
            print(f"  Match {i+1} (similarity: {event['similarity']:.2f}): {event['content'][:100]}...")
    except Exception as e:
        print(f"✗ Event search failed: {e}")
    
    print()


async def demo_relevant_profiles(memobase):
    """
    Demonstrates getting profiles relevant to current conversation
    """
    print("=== Relevant Profiles Demo ===")
    
    user_id = "demo_user_123"
    
    # Create a conversation context
    conversation = [
        OpenAICompatibleMessage(role="user", content="I'm planning my next hiking trip"),
        OpenAICompatibleMessage(role="assistant", content="Great! What type of hiking are you interested in?"),
        OpenAICompatibleMessage(role="user", content="I prefer scenic trails with waterfalls and nature views")
    ]
    
    try:
        # Get profiles relevant to current conversation
        relevant_profiles = await memobase.get_relevant_profiles(
            user_id=user_id,
            conversation=conversation,
            max_profiles=5,
            max_profile_token_size=2000
        )
        print(f"✓ Found {len(relevant_profiles)} relevant profiles")
        
        for profile in relevant_profiles:
            print(f"  Topic: {profile.topic}")
            for subtopic_name, entry in profile.subtopics.items():
                print(f"    - {subtopic_name}: {entry.content[:100]}...")
    except Exception as e:
        print(f"✗ Relevant profile retrieval failed: {e}")
    
    print()


async def demo_conversation_context(memobase):
    """
    Demonstrates generating comprehensive conversation context
    """
    print("=== Conversation Context Demo ===")
    
    user_id = "demo_user_123"
    
    conversation = [
        OpenAICompatibleMessage(role="user", content="What should I cook for dinner tonight?")
    ]
    
    try:
        # Generate comprehensive conversation context
        context = await memobase.get_conversation_context(
            user_id=user_id,
            conversation=conversation,
            max_token_size=1500,
            prefer_topics=["cooking", "dietary_preferences"],
            time_range_in_days=45,
            event_similarity_threshold=0.25,
            profile_event_ratio=0.6
        )
        print("✓ Generated conversation context")
        print(f"  Context length: {len(context)} characters")
        print(f"  Context preview: {context[:200]}...")
    except Exception as e:
        print(f"✗ Conversation context generation failed: {e}")
    
    print()


async def demo_profile_search(memobase):
    """
    Demonstrates searching profiles by text query
    """
    print("=== Profile Search Demo ===")
    
    user_id = "demo_user_123"
    
    try:
        # Search profiles by query
        searched_profiles = await memobase.search_profiles(
            user_id=user_id,
            query="favorite outdoor activities and hobbies",
            topics=["interests"],
            max_results=3
        )
        print(f"✓ Found {len(searched_profiles)} profiles matching the query")
        
        for profile in searched_profiles:
            print(f"  Topic: {profile.topic}")
            for subtopic_name, entry in profile.subtopics.items():
                print(f"    - {subtopic_name}: {entry.content[:100]}...")
    except Exception as e:
        print(f"✗ Profile search failed: {e}")
    
    print()


async def demo_buffer_management(memobase):
    """
    Demonstrates buffer management functionality
    """
    print("=== Buffer Management Demo ===")
    
    user_id = "demo_user_123"
    
    # Create a sample chat blob to add to buffer
    chat_blob = ChatBlob(
        messages=[
            OpenAICompatibleMessage(role="user", content="Testing buffer functionality"),
            OpenAICompatibleMessage(role="assistant", content="Buffer is working correctly!")
        ],
        type=BlobType.chat,
        created_at=None
    )
    
    try:
        # Add blob to buffer
        blob_id = await memobase.add_blob_to_buffer(
            user_id=user_id,
            blob=chat_blob
        )
        print(f"✓ Added blob to buffer with ID: {blob_id}")
    except Exception as e:
        print(f"✗ Failed to add blob to buffer: {e}")
        return
    
    try:
        # Check buffer status
        buffer_status = await memobase.detect_buffer_full_or_not(
            user_id=user_id,
            blob_type=BlobType.chat
        )
        print(f"✓ Buffer status: {buffer_status}")
    except Exception as e:
        print(f"✗ Failed to check buffer status: {e}")
    
    try:
        # Process buffer (this will extract memories from buffered blobs)
        process_result = await memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat
        )
        print(f"✓ Buffer processed successfully")
        if process_result:
            print(f"  Process result: {process_result}")
    except Exception as e:
        print(f"✗ Buffer processing failed: {e}")
    
    print()


async def demo_error_handling(memobase):
    """
    Demonstrates proper error handling
    """
    print("=== Error Handling Demo ===")
    
    try:
        # This will likely fail due to invalid user ID format or missing data
        profiles = await memobase.get_user_profiles("invalid_user_id_123456789")
        print(f"✓ Retrieved profiles: {len(profiles)} found")
    except Exception as e:
        print(f"✗ Expected error occurred: {type(e).__name__}: {e}")
    
    try:
        # Try to extract memories with empty blobs list
        result = await memobase.extract_memories(
            user_id="demo_user_123",
            blobs=[]  # Empty list
        )
        print(f"✓ Empty extraction result: {result}")
    except Exception as e:
        print(f"✗ Expected error for empty blobs: {type(e).__name__}: {e}")
    
    print()


async def main():
    """
    Main demo function that runs all API usage examples
    """
    print("LindormMemobase API Usage Demo")
    print("=" * 50)
    print()
    
    # Initialize memobase instance
    memobase = await initialize_memobase()
    
    # Run all demo functions
    # await demo_memory_extraction(memobase)
    await demo_profile_management(memobase)
    await demo_event_management(memobase)
    await demo_relevant_profiles(memobase)
    await demo_conversation_context(memobase)
    await demo_profile_search(memobase)
    # await demo_buffer_management(memobase)
    # await demo_error_handling(memobase)
    
    print("Demo completed successfully!")
    print()
    print("Key takeaways:")
    print("- Always handle exceptions appropriately")
    print("- Use async/await for all API methods")
    print("- Buffer management helps batch process blobs efficiently")
    print("- Profile and event searches use vector similarity")
    print("- Conversation context combines profiles and events for rich context")


if __name__ == "__main__":
    # Run the async demo
    asyncio.run(main())