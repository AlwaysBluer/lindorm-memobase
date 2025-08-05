"""
Profile Management Example

This example shows how to work with user profiles:
- Creating and updating profiles
- Managing profile topics and subtopics
- Querying profile information
"""

import asyncio
from lindormmemobase import MemoBaseAPI, Config
from lindormmemobase.models.types import Profile, ProfileEntry

async def profile_management_example():
    """Demonstrate profile management capabilities"""
    
    config = Config.load_config()
    api = MemoBaseAPI(config)
    
    user_id = "user123"
    
    # Create a sample profile entry
    profile_entry = ProfileEntry(
        topic="hobbies",
        subtopic="music",
        content="Plays guitar, learning jazz, enjoys improvisation",
        confidence=0.9,
        last_updated=None
    )
    
    # Create a profile
    profile = Profile(
        user_id=user_id,
        entries=[profile_entry],
        metadata={"source": "manual_entry"}
    )
    
    print(f"📋 Created profile for user {user_id}")
    print(f"   Topic: {profile_entry.topic}")
    print(f"   Subtopic: {profile_entry.subtopic}")
    print(f"   Content: {profile_entry.content}")
    
    # In a real application, you would store this profile
    # using the storage backend configured in your system
    
    # Example of querying profiles (pseudo-code)
    print("\n🔍 Profile query examples:")
    print("- Get all profiles for user")
    print("- Filter profiles by topic")
    print("- Search profiles by content")

if __name__ == "__main__":
    asyncio.run(profile_management_example())