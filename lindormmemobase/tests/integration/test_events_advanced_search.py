"""Integration tests for advanced event search filtering."""
import pytest
from datetime import datetime, timezone, timedelta
from lindormmemobase import LindormMemobase
from lindormmemobase.models.response import EventSearchFilters
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.config import Config


@pytest.fixture
async def memobase_with_events(integration_config):
    """Create a memobase instance and populate with test events."""
    config = integration_config
    memobase = LindormMemobase(config)
    
    # Reset storage for clean state
    await memobase.reset_all_storage(user_id="test_user_advanced")
    
    # Create test events with different topics, subtopics, and tags
    test_conversations = [
        # Life planning - travel events
        ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I want to travel to Europe next summer"),
                OpenAICompatibleMessage(role="assistant", content="That sounds exciting! Which countries are you interested in?")
            ],
            type=BlobType.chat
        ),
        # Life planning - career events
        ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I'm thinking about changing my career to data science"),
                OpenAICompatibleMessage(role="assistant", content="What aspects of data science interest you most?")
            ],
            type=BlobType.chat
        ),
        # Interests - cooking events
        ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I love cooking Italian food"),
                OpenAICompatibleMessage(role="assistant", content="What's your favorite Italian dish to make?")
            ],
            type=BlobType.chat
        ),
    ]
    
    # Add conversations to buffer and process
    for i, blob in enumerate(test_conversations):
        await memobase.add_blob_to_buffer(
            user_id="test_user_advanced",
            blob=blob,
            blob_id=f"test_blob_{i}",
            project_id="test_project"
        )
    
    # Process the buffer to create events
    await memobase.process_buffer(
        user_id="test_user_advanced",
        blob_type=BlobType.chat,
        project_id="test_project"
    )
    
    yield memobase
    
    # Cleanup
    await memobase.reset_all_storage(user_id="test_user_advanced")


@pytest.mark.asyncio
async def test_search_events_advanced_basic(memobase_with_events):
    """Test basic advanced search without filters (should work like search_events)."""
    memobase = memobase_with_events
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="travel",
        limit=10
    )
    
    assert isinstance(events, list)
    # Should find at least the travel-related event if embeddings are enabled


@pytest.mark.asyncio
async def test_search_events_advanced_with_topic_filter(memobase_with_events):
    """Test filtering by single topic."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(topics=["life_plan"])
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="future plans",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)
    # All returned events should have life_plan topic
    for event in events:
        if hasattr(event.event_data, 'profile_delta') and event.event_data.profile_delta:
            for delta in event.event_data.profile_delta:
                if delta.attributes and 'topic' in delta.attributes:
                    assert delta.attributes['topic'] == 'life_plan'


@pytest.mark.asyncio
async def test_search_events_advanced_with_multiple_topics(memobase_with_events):
    """Test filtering by multiple topics (OR logic)."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(topics=["life_plan", "interests"])
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="activities",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)
    # Events should have either life_plan or interests topic


@pytest.mark.asyncio
async def test_search_events_advanced_with_subtopic_filter(memobase_with_events):
    """Test filtering by subtopic."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(
        topics=["life_plan"],
        subtopics=["travel"]
    )
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="Europe",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_search_events_advanced_with_tag_filter(memobase_with_events):
    """Test filtering by event tags."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(tags=["preference", "interest"])
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="cooking",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_search_events_advanced_with_time_range(memobase_with_events):
    """Test filtering by time range."""
    memobase = memobase_with_events
    
    # Search with very short time range (should find recent events)
    filters = EventSearchFilters(time_range_in_days=1)
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="travel",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)
    # All events should be within the last day
    now = datetime.now(timezone.utc)
    for event in events:
        event_time = event.created_at
        if isinstance(event_time, datetime):
            time_diff = now - event_time.replace(tzinfo=timezone.utc)
            assert time_diff.days <= 1


@pytest.mark.asyncio
async def test_search_events_advanced_with_project_filter(memobase_with_events):
    """Test filtering by project_id."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(project_id="test_project")
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="travel",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_search_events_advanced_complex_filter(memobase_with_events):
    """Test complex multi-dimensional filtering."""
    memobase = memobase_with_events
    
    filters = EventSearchFilters(
        project_id="test_project",
        topics=["life_plan"],
        subtopics=["travel", "career"],
        time_range_in_days=7
    )
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="planning",
        limit=20,
        similarity_threshold=0.1,
        filters=filters
    )
    
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_search_events_advanced_empty_result(memobase_with_events):
    """Test that filtering with no matches returns empty list."""
    memobase = memobase_with_events
    
    # Filter with topic that doesn't exist
    filters = EventSearchFilters(topics=["nonexistent_topic"])
    
    events = await memobase.search_events_advanced(
        user_id="test_user_advanced",
        query="anything",
        limit=10,
        filters=filters
    )
    
    assert isinstance(events, list)
    assert len(events) == 0


@pytest.mark.asyncio
async def test_search_events_backward_compatibility(memobase_with_events):
    """Test that existing search_events still works (backward compatibility)."""
    memobase = memobase_with_events
    
    # Old method should still work
    events = await memobase.search_events(
        user_id="test_user_advanced",
        query="travel",
        limit=10,
        time_range_in_days=21,
        project_id="test_project"
    )
    
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_event_search_filters_defaults():
    """Test EventSearchFilters default values."""
    filters = EventSearchFilters()
    
    assert filters.project_id is None
    assert filters.time_range_in_days == 21
    assert filters.topics is None
    assert filters.subtopics is None
    assert filters.tags is None
    assert filters.tag_values is None


@pytest.mark.asyncio
async def test_event_search_filters_custom_values():
    """Test EventSearchFilters with custom values."""
    filters = EventSearchFilters(
        project_id="my_project",
        time_range_in_days=30,
        topics=["topic1", "topic2"],
        subtopics=["sub1"],
        tags=["tag1"],
        tag_values=["value1"]
    )
    
    assert filters.project_id == "my_project"
    assert filters.time_range_in_days == 30
    assert filters.topics == ["topic1", "topic2"]
    assert filters.subtopics == ["sub1"]
    assert filters.tags == ["tag1"]
    assert filters.tag_values == ["value1"]
