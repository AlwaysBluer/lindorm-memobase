"""
Basic Usage Example for LindormMemobase

This example demonstrates the core functionality of lindormmemobase:
- Creating a MemoBaseAPI instance
- Processing conversation blobs
- Extracting user profiles
- Basic memory operations
"""

import asyncio
from lindormmemobase import MemoBaseAPI, Blob, Config
from datetime import datetime

async def basic_usage_example():
    """Demonstrate basic usage of lindormmemobase"""
    
    # Initialize the API with configuration
    config = Config.load_config()
    api = MemoBaseAPI(config)
    
    # Create some sample conversation blobs
    blobs = [
        Blob(
            content="Hi, I'm John. I love playing guitar and I'm learning jazz.",
            timestamp=datetime.now(),
            user_id="user123",
            source="chat"
        ),
        Blob(
            content="I work as a software engineer at a tech startup.",
            timestamp=datetime.now(),
            user_id="user123", 
            source="chat"
        ),
        Blob(
            content="My favorite programming languages are Python and TypeScript.",
            timestamp=datetime.now(),
            user_id="user123",
            source="chat"
        )
    ]
    
    # Process the blobs to extract memory and profiles
    try:
        result = await api.process_blobs(blobs)
        
        if result.ok():
            response = result.data()
            print("✅ Successfully processed blobs!")
            print(f"Extracted {len(response.facts)} facts")
            print(f"Updated {len(response.profiles)} profiles")
            
            # Print extracted facts
            for fact in response.facts:
                print(f"📝 Fact: {fact}")
            
            # Print user profiles
            for profile in response.profiles:
                print(f"👤 Profile: {profile}")
                
        else:
            print(f"❌ Error processing blobs: {result.msg()}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(basic_usage_example())