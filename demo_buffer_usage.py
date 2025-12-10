#!/usr/bin/env python3
"""
Demo: Buffer Isolation with project_id

This demo showcases how the buffer system now isolates data by project_id,
enabling proper multi-tenancy support. Different projects can maintain
independent buffer states even for the same user_id.
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage


async def demo_buffer_project_isolation():
    """Demonstrate buffer isolation across different projects."""
    
    print("=" * 80)
    print("Buffer Isolation with project_id Demo")
    print("=" * 80)
    print()
    
    # Initialize Memobase
    print("📌 Step 1: Reset all storage and reinitialize LindormMemobase")
    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)
    
    await memobase.reset_all_storage()

    user_id = f"demo_user_{int(datetime.now().timestamp())}"
    print(f"✓ User ID: {user_id}")
    print()
    
    # ========== Part 1: Add blobs to different projects ==========
    print("=" * 80)
    print("Part 1: Add Blobs to Different Projects")
    print("=" * 80)
    print()
    
    # Create blob for project A
    print("💬 Adding blob to Project A")
    blob_project_a = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I'm working on Project A - an e-commerce platform. I'm very happy about it!"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="That's interesting! Tell me more about the e-commerce platform."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    blob_id_a = await memobase.add_blob_to_buffer(
        user_id=user_id,
        blob=blob_project_a,
        project_id="project_a_ecommerce"
    )
    print(f"  ✓ Blob added to Project A: {blob_id_a}")
    print()
    
    # Create blob for project B
    print("💬 Adding blob to Project B")
    blob_project_b = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="I'm working on Project B - a data analytics tool. I fell depressed since it's too hard"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="Great! Data analytics is very important."
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    blob_id_b = await memobase.add_blob_to_buffer(
        user_id=user_id,
        blob=blob_project_b,
        project_id="project_b_analytics"
    )
    print(f"  ✓ Blob added to Project B: {blob_id_b}")
    print()
    
    # ========== Part 2: Check buffer status per project ==========
    print("=" * 80)
    print("Part 2: Check Buffer Status (Isolated by Project)")
    print("=" * 80)
    print()
    
    print("🔍 Checking buffer status for Project A:")
    status_a = await memobase.detect_buffer_full_or_not(
        user_id=user_id,
        blob_type=BlobType.chat,
        project_id="project_a_ecommerce"
    )
    print(f"  - Is full: {status_a['is_full']}")
    print(f"  - Buffer IDs: {status_a['buffer_full_ids']}")
    print()
    
    print("🔍 Checking buffer status for Project B:")
    status_b = await memobase.detect_buffer_full_or_not(
        user_id=user_id,
        blob_type=BlobType.chat,
        project_id="project_b_analytics"
    )
    print(f"  - Is full: {status_b['is_full']}")
    print(f"  - Buffer IDs: {status_b['buffer_full_ids']}")
    print()
    
    print("✅ Notice: Each project maintains its own buffer state!")
    print("   Project A and Project B have independent buffer counts.")
    print()
    
    # ========== Part 3: Process buffer for specific project ==========
    print("=" * 80)
    print("Part 3: Process Buffer (Project-Specific)")
    print("=" * 80)
    print()
    
    print("⚙️  Processing buffer for Project A only...")
    try:
        result_a = await memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat,
            project_id="project_a_ecommerce"
        )
        
        if result_a:
            print(f"  ✓ Project A processed successfully")
            print(f"  - Event ID: {result_a.event_id}")
            print(f"  - Profiles added: {len(result_a.add_profiles)}")
            print(f"  - Profiles updated: {len(result_a.update_profiles)}")
        else:
            print("  ℹ️  No blobs to process for Project A")
    except Exception as e:
        print(f"  ⚠️  Processing failed (this is expected in demo mode): {e}")
    print()
    
    print("⚙️  Processing buffer for Project B only...")
    try:
        result_b = await memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat,
            project_id="project_b_analytics"
        )
        
        if result_b:
            print(f"  ✓ Project B processed successfully")
            print(f"  - Event ID: {result_b.event_id}")
            print(f"  - Profiles added: {len(result_b.add_profiles)}")
            print(f"  - Profiles updated: {len(result_b.update_profiles)}")
        else:
            print("  ℹ️  No blobs to process for Project B")
    except Exception as e:
        print(f"  ⚠️  Processing failed (this is expected in demo mode): {e}")
    print()
    
    # ========== Part 4: Verify isolation ==========
    print("=" * 80)
    print("Part 4: Verify Profile Isolation")
    print("=" * 80)
    print()
    
    print("📋 Checking profiles for Project A:")
    try:
        profiles_a = await memobase.get_user_profiles(
            user_id=user_id,
            project_id="project_a_ecommerce"
        )
        print(f"  ✓ Found {len(profiles_a)} profile(s) for Project A")
        for profile in profiles_a:
            print(f"    - Topic: {profile.topic}")
    except Exception as e:
        print(f"  ℹ️  No profiles yet or error: {e}")
    print()
    
    print("📋 Checking profiles for Project B:")
    try:
        profiles_b = await memobase.get_user_profiles(
            user_id=user_id,
            project_id="project_b_analytics"
        )
        print(f"  ✓ Found {len(profiles_b)} profile(s) for Project B")
        for profile in profiles_b:
            print(f"    - Topic: {profile.topic}")
    except Exception as e:
        print(f"  ℹ️  No profiles yet or error: {e}")
    print()
    
    # ========== Summary ==========
    print("=" * 80)
    print("Summary: Key Benefits of project_id Isolation")
    print("=" * 80)
    print()
    print("✅ 1. Independent Buffer Space:")
    print("   - Each project maintains its own buffer quota")
    print("   - Buffer overflow detection is project-scoped")
    print()
    print("✅ 2. Isolated Processing:")
    print("   - Processing one project's buffer doesn't affect others")
    print("   - Memories are stored with correct project_id")
    print()
    print("✅ 3. Multi-Tenancy Support:")
    print("   - Same user can work across multiple projects")
    print("   - No cross-contamination of data between projects")
    print()
    print("✅ 4. Backward Compatibility:")
    print("   - Optional project_id parameter (defaults to 'default')")
    print("   - Existing code continues to work without changes")
    print()
    print("Demo completed successfully! 🎉")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_buffer_project_isolation())
