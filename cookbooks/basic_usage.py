#!/usr/bin/env python3
"""
Basic Usage Example for LindormMemobase

This example demonstrates how to use the LindormMemobase class as the main
entry point for memory extraction and profile management functionality.
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, BlobType


async def basic_usage_example():
    """
    Demonstrate basic usage of LindormMemobase.
    """
    print("=== LindormMemobase Basic Usage Example ===\n")
    
    # Method 1: Create from default configuration with custom parameters
    print("1. Creating LindormMemobase instance with custom config...")
    
    try:
        memobase = LindormMemobase.from_config(
            language="en",
            best_llm_model="gpt-4o-mini",
            # Note: In real usage, set your API key:
            # llm_api_key="your-openai-api-key"
        )
        
        print(f"   Language: {memobase.config.language}")
        print(f"   Model: {memobase.config.best_llm_model}")
        print(f"   Embedding Provider: {memobase.config.embedding_provider}")
        
    except Exception as e:
        print(f"   Note: {e}")
        print("   This is expected without API keys configured")
        return
    
    # 2. Create conversation blobs
    print("\n2. Creating conversation blobs...")
    
    blobs = [
        memobase.create_blob(
            content="I love playing jazz guitar, especially Charlie Parker's compositions",
            blob_type=BlobType.chat
        ),
        memobase.create_blob(
            content="I'm learning Python programming and working on machine learning projects",
            blob_type=BlobType.chat
        ),
        memobase.create_blob(
            content="I prefer working from cafes in the morning with good coffee",
            blob_type=BlobType.chat
        )
    ]
    
    print(f"   Created {len(blobs)} conversation blobs")
    for i, blob in enumerate(blobs, 1):
        print(f"   Blob {i}: {blob.content[:60]}...")
    
    # 3. Extract facts from individual content
    print("\n3. Extracting facts from single content...")
    
    try:
        result = await memobase.extract_facts(
            user_id="demo_user",
            content="I work as a software engineer at a tech startup in San Francisco",
            source="profile_update"
        )
        
        if result.ok():
            print("   ✓ Facts extracted successfully!")
            print(f"   Response: {result.data()}")
        else:
            print(f"   ✗ Extraction failed: {result.msg()}")
    
    except Exception as e:
        print(f"   Note: Would extract facts in real usage (API key needed): {e}")
    
    # 4. Process multiple blobs for memory extraction
    print("\n4. Processing blobs for memory extraction...")
    
    try:
        result = await memobase.process_memories(
            user_id="demo_user",
            blobs=blobs
        )
        
        if result.ok():
            print("   ✓ Memory processing successful!")
            response = result.data()
            print(f"   Extracted {len(response.facts)} facts")
            print(f"   Profile updates: {len(response.profile_updates)} topics")
        else:
            print(f"   ✗ Processing failed: {result.msg()}")
    
    except Exception as e:
        print(f"   Note: Would process memories in real usage (API key needed): {e}")
    
    # 5. Profile management
    print("\n5. Profile management operations...")
    
    try:
        # Get user profile
        profile_result = await memobase.get_user_profile("demo_user")
        if profile_result.ok():
            profiles = profile_result.data()
            print(f"   User has {len(profiles)} profile topics")
            
            # Get topic names
            topics_result = await memobase.get_profile_topics("demo_user")
            if topics_result.ok():
                topics = topics_result.data()
                print(f"   Topics: {', '.join(topics)}")
        else:
            print(f"   Note: Profile not found (expected for demo)")
    
    except Exception as e:
        print(f"   Note: Would manage profiles in real usage: {e}")
    
    # 6. Configuration management
    print("\n6. Configuration management...")
    
    current_config = memobase.get_config()
    print(f"   Current language: {current_config.language}")
    print(f"   Current model: {current_config.best_llm_model}")
    
    # Update configuration
    memobase.update_config(
        language="zh",
        thinking_llm_model="o1-preview"
    )
    
    print(f"   Updated language: {memobase.config.language}")
    print(f"   Updated thinking model: {memobase.config.thinking_llm_model}")
    
    print("\n=== Basic Usage Example Complete ===")
    print("To use with real LLM processing:")
    print("1. Set MEMOBASE_LLM_API_KEY in your .env file")
    print("2. Optionally set MEMOBASE_EMBEDDING_API_KEY")
    print("3. Configure storage backends if needed")


if __name__ == "__main__":
    asyncio.run(basic_usage_example())