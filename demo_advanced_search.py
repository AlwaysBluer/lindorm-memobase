#!/usr/bin/env python3
"""
Demo script showing advanced event search filtering capabilities.

This script demonstrates how to use the new search_events_advanced method
with EventSearchFilters to perform fine-grained event retrieval.
"""
import asyncio
from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.response import EventSearchFilters
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage


async def main():
    print("=" * 60)
    print("Advanced Event Search Demo")
    print("=" * 60)
    adding = True
    # Initialize LindormMemobase
    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)
    
    user_id = f"demo_user_advanced_search_{uuid.uuid4().hex}"
    project_id = "demo_project"
    
    if adding:
    # Clean up any existing data
    # print("\n1. Resetting storage for clean demo...")
        # await memobase.reset_all_storage()
    # Create sample conversations with different topics
        print("\n2. Creating sample conversations...")
    
        conversations = [
            # Life planning - travel
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I want to travel to Europe next summer for 2 weeks"),
                    OpenAICompatibleMessage(role="assistant", content="That sounds exciting! Which countries interest you?"),
                    OpenAICompatibleMessage(role="user", content="I'm thinking France, Italy, and Spain"),
                ],
                type=BlobType.chat
            ),
        ]
    
        # Add conversations to buffer
        for i, conv in enumerate(conversations):
            await memobase.add_blob_to_buffer(
                user_id=user_id,
                blob=conv,
                blob_id=f"demo_blob_{i}",
                project_id=project_id
            )
            print(f"   Added {len(conversations)} conversations to buffer")
            # Process buffer to extract events
            print("\n3. Processing buffer to extract events...")
            result = await memobase.process_buffer(
                user_id=user_id,
                blob_type=BlobType.chat,
                project_id=project_id
            )
            print("   Buffer processed successfully")
    
        # Wait a bit for indexing
        await asyncio.sleep(2)
    
    # Example 1: Basic search (no filters)
    print("\n" + "=" * 60)
    print("Example 1: Basic search without filters")
    print("=" * 60)
    
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="travel plans",
        limit=10
    )
    print(f"Found {len(events)} events for 'travel plans'")
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Similarity: {event.similarity:.3f}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 2: Filter by topic
    print("\n" + "=" * 60)
    print("Example 2: Filter by single topic")
    print("=" * 60)
    
    filters = EventSearchFilters(topics=["plans"])
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="future plans",
        limit=10,
        filters=filters
    )
    print(f"Found {len(events)} events with topic 'plans'")
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Similarity: {event.similarity:.3f}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 3: Filter by multiple topics (OR logic)
    print("\n" + "=" * 60)
    print("Example 3: Filter by multiple topics (OR logic)")
    print("=" * 60)
    
    filters = EventSearchFilters(topics=["personal_growth", "plans"])
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="activities I enjoy",
        limit=10,
        filters=filters
    )
    print(f"Found {len(events)} events with topics 'personal_growth' OR 'plans'")
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Similarity: {event.similarity:.3f}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 4: Filter by topic and subtopic
    print("\n" + "=" * 60)
    print("Example 4: Filter by topic and subtopic")
    print("=" * 60)
    
    filters = EventSearchFilters(
        topics=["personal_growth"],
        subtopics=["hobbies"]
    )
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="vacation",
        limit=10,
        filters=filters
    )
    print(f"Found {len(events)} events with topic 'plans' AND subtopic 'personal_aspirations'")
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Similarity: {event.similarity:.3f}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 5: Filter by time range
    print("\n" + "=" * 60)
    print("Example 5: Filter by time range")
    print("=" * 60)
    
    filters = EventSearchFilters(time_range_in_days=1)  # Only events from last day
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="anything",
        limit=10,
        filters=filters
    )
    print(f"Found {len(events)} events from the last 1 day")
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Created: {event.created_at}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 6: Complex multi-dimensional filtering
    print("\n" + "=" * 60)
    print("Example 6: Complex multi-dimensional filtering")
    print("=" * 60)
    
    filters = EventSearchFilters(
        project_id=project_id,
        topics=["plans", "personal_growth"],
        time_range_in_days=7,
        tags=["mental_health"],
        tag_values=["happiness"]
    )
    events = await memobase.search_events_advanced(
        user_id=user_id,
        query="planning and goals",
        limit=20,
        similarity_threshold=0.1,
        filters=filters
    )
    print(f"Found {len(events)} events with complex filters:")
    print(f"  - Project: {project_id}")
    print(f"  - Topics: personal_growth OR plans")
    print(f"  - Time range: last 7 days")
    print(f"  - Similarity threshold: 0.1")
    
    for i, event in enumerate(events[:3], 1):
        print(f"\n  {i}. Similarity: {event.similarity:.3f}")
        if event.event_data and event.event_data.event_tip:
            print(f"     Tip: {event.event_data.event_tip}\n...")
    
    # Example 7: Compare with basic search_events
    print("\n" + "=" * 60)
    print("Example 7: Backward compatibility - using search_events")
    print("=" * 60)
    
    events_old = await memobase.search_events(
        user_id=user_id,
        query="travel",
        limit=10,
        project_id=project_id
    )
    print(f"Found {len(events_old)} events using old search_events method")
    print("(This method still works without any changes)")
    
    # Cleanup
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)
    # await memobase.reset_all_storage(user_id=user_id)


if __name__ == "__main__":
    asyncio.run(main())
