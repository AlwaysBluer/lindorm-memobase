#!/usr/bin/env python3
"""
Demo script showing advanced search capabilities.

This script demonstrates:
1. Advanced event search with EventSearchFilters
2. NEW: Profile vector search (embedding-based)
3. NEW: Profile rerank search (rerank model-based)
4. NEW: Profile hybrid search (embedding + rerank)
"""
from re import T
import uuid
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
    # user_id = f"demo_user_advanced_search_4038a5bfc33342379dbb3bf51bb11187"
    project_id = "demo_project"
    
    if adding:
        print("\n2. Creating sample conversations...")
        conversations = [
            # Travel planning
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I want to travel to Europe next summer for 2 weeks"),
                    OpenAICompatibleMessage(role="assistant", content="That sounds exciting! Which countries interest you?"),
                    OpenAICompatibleMessage(role="user", content="I'm thinking France, Italy, and Spain"),
                ],
                type=BlobType.chat
            ),
            
            # Career - personal_narrative & life_circumstances
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I just got promoted to senior engineer at my company"),
                    OpenAICompatibleMessage(role="assistant", content="Congratulations! How do you feel about this new role?"),
                    OpenAICompatibleMessage(role="user", content="I'm excited but also a bit nervous. It's a big step in my career journey"),
                    OpenAICompatibleMessage(role="assistant", content="That's completely normal. What aspects make you nervous?"),
                    OpenAICompatibleMessage(role="user", content="Leading a team of 5 people. I've never managed others before"),
                ],
                type=BlobType.chat
            ),
            
            # Education - life_circumstances
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I'm thinking about going back to school for a master's degree"),
                    OpenAICompatibleMessage(role="assistant", content="That's a significant decision. What field are you interested in?"),
                    OpenAICompatibleMessage(role="user", content="Computer Science with a focus on AI. I want to transition from web development to machine learning"),
                    OpenAICompatibleMessage(role="assistant", content="Are you planning to study full-time or part-time?"),
                    OpenAICompatibleMessage(role="user", content="Part-time, so I can keep working. It'll take 3 years instead of 2"),
                ],
                type=BlobType.chat
            ),
            
            # Identity journey & self-acceptance - personal_narrative
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I've been reflecting a lot on who I am lately"),
                    OpenAICompatibleMessage(role="assistant", content="Self-reflection can be really valuable. What's been on your mind?"),
                    OpenAICompatibleMessage(role="user", content="I used to be so shy and anxious in social situations. Now I feel more confident"),
                    OpenAICompatibleMessage(role="assistant", content="That's wonderful growth. What helped you change?"),
                    OpenAICompatibleMessage(role="user", content="Therapy and pushing myself to join a public speaking club. I'm learning to accept myself"),
                ],
                type=BlobType.chat
            ),
            
            # Family status - life_circumstances
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="My sister just had her first baby. I'm an uncle now!"),
                    OpenAICompatibleMessage(role="assistant", content="How exciting! How does it feel?"),
                    OpenAICompatibleMessage(role="user", content="Amazing! It makes me think about my own family plans for the future"),
                    OpenAICompatibleMessage(role="assistant", content="Are you thinking about starting a family yourself?"),
                    OpenAICompatibleMessage(role="user", content="Maybe in a few years. My partner and I are focusing on our careers right now"),
                ],
                type=BlobType.chat
            ),
            
            # Living situation - life_circumstances
            ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role="user", content="I finally moved out of my parents' house last month"),
                    OpenAICompatibleMessage(role="assistant", content="That's a big life change! How's living on your own?"),
                    OpenAICompatibleMessage(role="user", content="It's been great. I rented a one-bedroom apartment downtown, close to my office"),
                    OpenAICompatibleMessage(role="assistant", content="Are you adjusting well to independent living?"),
                    OpenAICompatibleMessage(role="user", content="Yes! Though I'm still learning to cook properly. Been eating a lot of takeout"),
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
    
    # ================================================================
    # NEW: Profile Vector Search Examples
    # ================================================================
    
    print("\n" + "=" * 60)
    print("NEW FEATURE: Profile Search APIs")
    print("=" * 60)
    print("\nThese new APIs provide optimized profile search without LLM-based filtering:")
    print("  1. search_profiles_by_embedding - Fast vector similarity search")
    print("  2. search_profiles_with_rerank - Rerank model for accurate relevance")
    print("  3. search_profiles_hybrid - Best of both: embedding + rerank")
    
    # Example 8: Profile search by embedding (vector similarity)
    print("\n" + "=" * 60)
    print("Example 8: Profile search by embedding (vector similarity)")
    print("=" * 60)
    
    try:
        profiles = await memobase.search_profiles_by_embedding(
            user_id=user_id,
            query="travel destinations",
            max_results=5,
            min_score=0.3,
            project_id=project_id
        )
        print(f"Found {len(profiles)} profiles via embedding search")
        for i, profile in enumerate(profiles[:3], 1):
            print(f"\n  {i}. Topic: {profile.topic}")
            for subtopic, entry in list(profile.subtopics.items())[:2]:
                print(f"     {subtopic}: {entry.content[:100]}...")
    except Exception as e:
        print(f"   (Embedding search requires embedding to be enabled: {e})")
    
    # Example 9: Profile search with rerank model
    print("\n" + "=" * 60)
    print("Example 9: Profile search with rerank model")
    print("=" * 60)
    try:
        profiles = await memobase.search_profiles_with_rerank(
            user_id=user_id,
            query="What are my travel preferences?",
            max_results=5,
            combine_by_topic=True,
            project_id=project_id
        )
        print(f"Found {len(profiles)} profiles via rerank search")
        for i, profile in enumerate(profiles[:3], 1):
            print(f"\n  {i}. Topic: {profile.topic}")
            for subtopic, entry in list(profile.subtopics.items())[:2]:
                print(f"     {subtopic}: {entry.content[:100]}...")
    except Exception as e:
        print(f"   (Rerank search requires rerank API to be configured: {e})")
    
    # Example 10: Hybrid search (embedding + rerank)
    print("\n" + "=" * 60)
    print("Example 10: Hybrid search (embedding + rerank)")
    print("=" * 60)
    try:
        profiles = await memobase.search_profiles_hybrid(
            user_id=user_id,
            query="best vacation spots",
            max_results=5,
            embedding_candidates=20,
            min_embedding_score=0.2,
            project_id=project_id
        )
        print(f"Found {len(profiles)} profiles via hybrid search")
        for i, profile in enumerate(profiles[:3], 1):
            print(f"\n  {i}. Topic: {profile.topic}")
            for subtopic, entry in list(profile.subtopics.items())[:2]:
                print(f"     {subtopic}: {entry.content[:100]}...")
    except Exception as e:
        print(f"   (Hybrid search requires both embedding and rerank: {e})")
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)
    # await memobase.reset_all_storage(user_id=user_id)


if __name__ == "__main__":
    asyncio.run(main())
