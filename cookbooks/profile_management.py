#!/usr/bin/env python3
"""
Profile Management Example for LindormMemobase

This example demonstrates how to work with user profiles using the
LindormMemobase class:
- Creating and managing user profiles
- Working with topics and subtopics
- Profile queries and updates
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, create_config
from lindormmemobase.models.types import Profile, ProfileEntry


async def profile_management_example():
    """
    Demonstrate comprehensive profile management capabilities.
    """
    print("=== LindormMemobase Profile Management Example ===\n")
    
    # 1. Initialize LindormMemobase with custom configuration
    print("1. Initializing LindormMemobase...")
    
    try:
        # Create custom config for profile management
        config = create_config(
            language="en",
            profile_strict_mode=True,
            profile_validate_mode=True,
            max_profile_subtopics=20,
            # Note: In real usage, set API keys:
            # llm_api_key="your-openai-api-key"
        )
        
        memobase = LindormMemobase(config)
        print(f"   Profile strict mode: {config.profile_strict_mode}")
        print(f"   Max subtopics: {config.max_profile_subtopics}")
        
    except Exception as e:
        print(f"   Note: {e}")
        print("   This is expected without API keys configured")
        return
    
    user_id = "profile_demo_user"
    
    # 2. Create sample profile entries manually
    print(f"\n2. Creating sample profile entries for user: {user_id}")
    
    # Create sample profiles
    sample_profiles = {
        "hobbies": Profile(
            topic="hobbies",
            subtopics={
                "music": ProfileEntry(
                    content="Plays jazz guitar, loves Charlie Parker, practices daily",
                    confidence=0.9,
                    last_updated=datetime.now().timestamp()
                ),
                "sports": ProfileEntry(
                    content="Enjoys tennis on weekends, intermediate level player",
                    confidence=0.8,
                    last_updated=datetime.now().timestamp()
                )
            },
            metadata={"created_by": "manual_entry"}
        ),
        
        "career": Profile(
            topic="career",
            subtopics={
                "current_role": ProfileEntry(
                    content="Software engineer at tech startup, 5 years experience",
                    confidence=0.95,
                    last_updated=datetime.now().timestamp()
                ),
                "skills": ProfileEntry(
                    content="Python, JavaScript, machine learning, cloud computing",
                    confidence=0.85,
                    last_updated=datetime.now().timestamp()
                )
            },
            metadata={"source": "conversation_analysis"}
        ),
        
        "preferences": Profile(
            topic="preferences",
            subtopics={
                "work_style": ProfileEntry(
                    content="Prefers working from cafes, morning person, likes good coffee",
                    confidence=0.75,
                    last_updated=datetime.now().timestamp()
                )
            },
            metadata={"inferred": True}
        )
    }
    
    print(f"   Created {len(sample_profiles)} profile topics:")
    for topic, profile in sample_profiles.items():
        print(f"     - {topic}: {len(profile.subtopics)} subtopics")
    
    # 3. Save profiles (simulate storage)
    print("\n3. Profile storage operations...")
    
    try:
        # Save profiles
        save_result = await memobase.update_user_profile(user_id, sample_profiles)
        if save_result.ok():
            print("   ✓ Profiles saved successfully")
        else:
            print(f"   ✗ Failed to save profiles: {save_result.msg()}")
    
    except Exception as e:
        print(f"   Note: Would save to configured storage in real usage: {e}")
    
    # 4. Retrieve and query profiles
    print("\n4. Profile retrieval and queries...")
    
    try:
        # Get all user profiles
        profiles_result = await memobase.get_user_profile(user_id)
        if profiles_result.ok():
            profiles = profiles_result.data()
            print(f"   Retrieved {len(profiles)} profile topics")
            
            # Display profile summary
            for topic, profile in profiles.items():
                print(f"     Topic '{topic}': {len(profile.subtopics)} subtopics")
                for subtopic, entry in profile.subtopics.items():
                    confidence_str = f"({entry.confidence:.1%})"
                    print(f"       - {subtopic}: {entry.content[:50]}... {confidence_str}")
        
        # Get topic names only
        topics_result = await memobase.get_profile_topics(user_id)
        if topics_result.ok():
            topics = topics_result.data()
            print(f"   Available topics: {', '.join(topics)}")
    
    except Exception as e:
        print(f"   Note: Would retrieve from storage in real usage: {e}")
    
    # 5. Profile updates through conversation processing
    print("\n5. Updating profiles through conversation processing...")
    
    try:
        # Process new conversation that would update profiles
        new_conversations = [
            "I just started learning violin in addition to guitar",
            "I got promoted to senior software engineer last month",
            "I discovered I really enjoy working late at night, not mornings"
        ]
        
        for i, content in enumerate(new_conversations, 1):
            print(f"   Processing conversation {i}: '{content[:40]}...'")
            
            # This would extract facts and update profiles
            result = await memobase.extract_facts(
                user_id=user_id,
                content=content,
                source="conversation_update"
            )
            
            if result.ok():
                print(f"     ✓ Successfully processed conversation {i}")
                # In real usage, this would automatically update the user's profile
            else:
                print(f"     ✗ Failed to process conversation {i}: {result.msg()}")
    
    except Exception as e:
        print(f"   Note: Would process and update profiles in real usage: {e}")
    
    # 6. Profile analysis and insights
    print("\n6. Profile analysis capabilities...")
    
    # Demonstrate what profile analysis could provide
    analysis_examples = [
        "Profile completeness: 75% (missing location, education topics)",
        "Confidence distribution: High (60%), Medium (30%), Low (10%)",
        "Most active topics: hobbies, career",
        "Recent updates: 3 changes in last week",
        "Potential conflicts: work preference contradiction detected"
    ]
    
    print("   Profile insights (example analysis):")
    for insight in analysis_examples:
        print(f"     • {insight}")
    
    # 7. Configuration impact on profiles
    print("\n7. Configuration impact on profiles...")
    
    print(f"   Current profile settings:")
    print(f"     - Strict mode: {memobase.config.profile_strict_mode}")
    print(f"     - Validation: {memobase.config.profile_validate_mode}")
    print(f"     - Max subtopics: {memobase.config.max_profile_subtopics}")
    print(f"     - Language: {memobase.config.language}")
    
    # Update configuration to show impact
    memobase.update_config(
        profile_strict_mode=False,
        max_profile_subtopics=10
    )
    
    print(f"   Updated settings:")
    print(f"     - Strict mode: {memobase.config.profile_strict_mode}")
    print(f"     - Max subtopics: {memobase.config.max_profile_subtopics}")
    
    print("\n=== Profile Management Example Complete ===")
    print("Key profile management features:")
    print("• Structured topic/subtopic organization")
    print("• Confidence tracking for entries")
    print("• Automatic updates from conversations")
    print("• Configurable validation and limits")
    print("• Storage backend integration")


if __name__ == "__main__":
    asyncio.run(profile_management_example())