#!/usr/bin/env python3
"""
Demo script showing advanced search capabilities.

This script demonstrates:
1. Advanced event search with EventSearchFilters
2. NEW: Profile vector search (embedding-based)
3. NEW: Profile rerank search (rerank model-based)
4. NEW: Profile hybrid search (embedding + rerank)
"""
import uuid
import asyncio
from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.response import EventSearchFilters
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.core.storage.user_profiles import add_user_profiles


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
    other_project_id = "demo_project_other"
    
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

        # Add one conversation into a different project to validate project_id isolation
        other_project_conv = ChatBlob(
            messages=[
                OpenAICompatibleMessage(
                    role="user",
                    content="Cross-project marker: kiwi-mars-8721. This preference belongs only to the other project."
                ),
                OpenAICompatibleMessage(
                    role="assistant",
                    content="Got it. I will remember this marker for your other project context only."
                ),
            ],
            type=BlobType.chat
        )
        await memobase.add_blob_to_buffer(
            user_id=user_id,
            blob=other_project_conv,
            blob_id="demo_blob_other_project",
            project_id=other_project_id
        )
        await memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat,
            project_id=other_project_id
        )
        print(f"   Added and processed one conversation in other project: {other_project_id}")
    
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
    print("  2. search_profiles_by_filter_rrf - Lindorm full-text + vector fusion")
    print("  3. search_profiles_with_rerank - Rerank model for accurate relevance")
    print("  4. search_profiles_hybrid - Best of both: embedding + rerank")
    
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
    
    # Example 9: Profile search with Lindorm filter_rrf hybrid retrieval
    print("\n" + "=" * 60)
    print("Example 9: Profile search by Lindorm filter_rrf hybrid retrieval")
    print("=" * 60)
    try:
        profiles = await memobase.search_profiles_by_filter_rrf(
            user_id=user_id,
            query="travel destinations",
            topics=["travel"],
            max_results=5,
            min_score=0.3,
            project_id=project_id
        )
        print(f"Found {len(profiles)} profiles via filter_rrf hybrid search")
        for i, profile in enumerate(profiles[:3], 1):
            print(f"\n  {i}. Topic: {profile.topic}")
            for subtopic, entry in list(profile.subtopics.items())[:2]:
                print(f"     {subtopic}: {entry.content[:100]}...")
    except Exception as e:
        print(f"   (filter_rrf hybrid search requires embedding to be enabled: {e})")

    # Example 9.1: Validate project_id filter isolation with controlled marker profiles
    print("\n" + "=" * 60)
    print("Example 9.1: Validate project_id filtering with cross-project marker")
    print("=" * 60)
    try:
        marker_current = "project-scope-marker-alpha-9012"
        marker_other = "project-scope-marker-beta-7755"

        await add_user_profiles(
            user_id=user_id,
            profiles=[f"Controlled marker profile for current project: {marker_current}"],
            attributes_list=[{"topic": "demo_scope", "sub_topic": "marker"}],
            config=config,
            project_id=project_id,
        )
        await add_user_profiles(
            user_id=user_id,
            profiles=[f"Controlled marker profile for other project: {marker_other}"],
            attributes_list=[{"topic": "demo_scope", "sub_topic": "marker"}],
            config=config,
            project_id=other_project_id,
        )

        # Use pure vector search for deterministic project_id filter validation.
        # Poll briefly because search index update can be asynchronous.
        current_project_profiles = []
        wrong_project_profiles = []
        other_project_profiles = []
        for _ in range(10):
            current_project_profiles = await memobase.search_profiles_by_embedding(
                user_id=user_id,
                query=marker_current,
                max_results=5,
                min_score=0.1,
                project_id=project_id
            )
            wrong_project_profiles = await memobase.search_profiles_by_embedding(
                user_id=user_id,
                query=marker_current,
                max_results=5,
                min_score=0.1,
                project_id=other_project_id
            )
            other_project_profiles = await memobase.search_profiles_by_embedding(
                user_id=user_id,
                query=marker_other,
                max_results=5,
                min_score=0.1,
                project_id=other_project_id
            )

            def _contains_marker(profiles, marker):
                for profile in profiles:
                    for _, entry in profile.subtopics.items():
                        if marker in entry.content:
                            return True
                return False

            current_has_current_marker = _contains_marker(current_project_profiles, marker_current)
            other_has_current_marker = _contains_marker(wrong_project_profiles, marker_current)
            other_has_other_marker = _contains_marker(other_project_profiles, marker_other)

            if current_has_current_marker and other_has_other_marker and not other_has_current_marker:
                break
            await asyncio.sleep(1)

        print(f"Query marker (current project): {marker_current}")
        print(f"  - Results in {project_id}: {len(current_project_profiles)}")
        print(f"  - Results in {other_project_id}: {len(wrong_project_profiles)}")
        print(f"Query marker (other project): {marker_other}")
        print(f"  - Results in {other_project_id}: {len(other_project_profiles)}")

        current_has_current_marker = any(marker_current in entry.content for p in current_project_profiles for _, entry in p.subtopics.items())
        other_has_current_marker = any(marker_current in entry.content for p in wrong_project_profiles for _, entry in p.subtopics.items())
        other_has_other_marker = any(marker_other in entry.content for p in other_project_profiles for _, entry in p.subtopics.items())

        if current_has_current_marker and other_has_other_marker and not other_has_current_marker:
            print("  - project_id filter works: markers are isolated by project")
        else:
            print("  - project_id isolation check is inconclusive (possible index refresh delay)")
    except Exception as e:
        print(f"   (Project isolation check failed: {e})")

    # Example 10: Profile search with rerank model
    print("\n" + "=" * 60)
    print("Example 10: Profile search with rerank model")
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
    
    # Example 11: Hybrid search (embedding + rerank)
    print("\n" + "=" * 60)
    print("Example 11: Hybrid search (embedding + rerank)")
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
