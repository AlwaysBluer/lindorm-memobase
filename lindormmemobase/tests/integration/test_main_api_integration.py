"""
Integration tests for main API (LindormMemobase class).

These tests verify end-to-end workflows with real LLM and storage services.
For LindormAI, credentials are loaded from .env (no separate API key needed).
"""

import pytest
from datetime import datetime
from lindormmemobase.main import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, DocBlob, OpenAICompatibleMessage, BlobType
from lindormmemobase.core.storage.manager import StorageManager


@pytest.mark.integration
@pytest.mark.asyncio
class TestLindormMemobaseIntegration:
    """Integration tests for LindormMemobase API."""
    
    @pytest.fixture
    def memobase(self, integration_config):
        """Create LindormMemobase instance for testing."""
        return LindormMemobase(integration_config)
    
    async def test_initialization_workflow(self, integration_config):
        """Test complete initialization workflow."""
        # Should initialize without errors
        memobase = LindormMemobase(integration_config)
        
        assert memobase.config is not None
        assert memobase.config.language in ["en", "zh"]
    
    async def test_from_yaml_workflow(self, temp_yaml_config):
        """Test initialization from YAML file."""
        memobase = LindormMemobase.from_yaml_file(str(temp_yaml_config))
        
        assert memobase.config.llm_api_key == "test-yaml-key"
    
    async def test_from_config_workflow(self):
        """Test initialization from parameters."""
        memobase = LindormMemobase.from_config(
            language="en",
            llm_api_key="test-key",
            best_llm_model="gpt-4o-mini",
            test_skip_persist=True
        )
        
        assert memobase.config.language == "en"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMemoryExtractionIntegration:
    """Integration tests for end-to-end memory extraction with real LLM."""
    
    @pytest.fixture
    async def memobase(self, integration_config):
        """Create memobase with integration config and cleanup after test."""
        # Ensure clean storage state
        if StorageManager.is_initialized():
            StorageManager.cleanup()
        
        memobase = LindormMemobase(integration_config)
        yield memobase
        
        # Cleanup after test
        if StorageManager.is_initialized():
            StorageManager.cleanup()
    
    async def test_add_blob_to_buffer_and_check_status(self, memobase, integration_config):
        """Test adding blobs to buffer and checking buffer status."""
        user_id = f"test_buffer_{datetime.now().timestamp()}"
        
        print(f"\n{'='*80}")
        print(f"Test: Add Blob to Buffer")
        print(f"User: {user_id}")
        print(f"LLM: {integration_config.llm_style} - {integration_config.best_llm_model}")
        print(f"{'='*80}\n")
        
        # Create a chat blob
        chat_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I love traveling to Japan"),
                OpenAICompatibleMessage(role="assistant", content="That's wonderful! What attracts you to Japan?"),
                OpenAICompatibleMessage(role="user", content="I especially enjoy cherry blossoms in spring and temples in Kyoto")
            ],
            type=BlobType.chat,
            created_at=datetime.now()
        )
        
        # Add blob to buffer
        blob_id = await memobase.add_blob_to_buffer(
            user_id=user_id,
            blob=chat_blob
        )
        
        print(f"✓ Added blob to buffer: {blob_id}")
        assert blob_id is not None
        
        # Check buffer status
        status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
        
        print(f"✓ Buffer status retrieved")
        print(f"  - Is full: {status['is_full']}")
        print(f"  - Full IDs: {status['buffer_full_ids']}\n")
        
        assert 'is_full' in status
        assert 'buffer_full_ids' in status
    
    async def test_extract_memories_from_chat_blob(self, memobase, integration_config):
        """Test complete memory extraction workflow with LLM.
        
        This tests:
        1. Creating a chat blob
        2. Extracting memories using LLM
        3. Verifying profiles are stored
        4. Retrieving stored profiles
        """
        user_id = f"test_extract_{datetime.now().timestamp()}"
        project_id = "test_memory_extraction"
        
        print(f"\n{'='*80}")
        print(f"Test: Complete Memory Extraction Workflow")
        print(f"User: {user_id}")
        print(f"Project: {project_id}")
        print(f"LLM: {integration_config.llm_style} - {integration_config.best_llm_model}")
        print(f"Embedding: {integration_config.embedding_provider} - {integration_config.embedding_model}")
        print(f"{'='*80}\n")
        
        # Create chat blob with rich user information
        chat_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(
                    role="user",
                    content="I'm planning a trip to Japan next spring. I love cherry blossoms!"
                ),
                OpenAICompatibleMessage(
                    role="assistant",
                    content="That sounds amazing! Cherry blossom season in Japan is beautiful. When in spring are you thinking?"
                ),
                OpenAICompatibleMessage(
                    role="user",
                    content="Probably late March or early April. I also want to visit temples in Kyoto and try authentic ramen."
                ),
                OpenAICompatibleMessage(
                    role="assistant",
                    content="Great choices! Kyoto has stunning temples. Do you have any dietary restrictions for the ramen?"
                ),
                OpenAICompatibleMessage(
                    role="user",
                    content="No restrictions, I eat everything. I'm particularly interested in trying tonkotsu ramen."
                )
            ],
            type=BlobType.chat,
            created_at=datetime.now()
        )
        
        print("Step 1: Extracting memories from chat using LLM...")
        try:
            # Extract memories - this calls LLM to analyze and structure the information
            extraction_result = await memobase.extract_memories(
                user_id=user_id,
                blobs=[chat_blob],
                project_id=project_id
            )
            
            print(f"✓ Memory extraction completed")
            print(f"  Result type: {type(extraction_result).__name__}")
            assert extraction_result is not None
            
        except Exception as e:
            print(f"✗ Memory extraction failed: {str(e)}")
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                print("\n⚠ Authentication Error - Check credentials:")
                if integration_config.llm_style == "lindormai":
                    print("  For LindormAI, verify:")
                    print("    - MEMOBASE_LINDORM_USERNAME in .env")
                    print("    - MEMOBASE_LINDORM_PASSWORD in .env")
                    print("    - MEMOBASE_LLM_BASE_URL is correct")
                else:
                    print("  For OpenAI, verify:")
                    print("    - MEMOBASE_LLM_API_KEY in .env")
            raise
        
        print("\nStep 2: Retrieving stored user profiles...")
        # Retrieve profiles to verify they were stored
        profiles = await memobase.get_user_profiles(
            user_id=user_id,
            project_id=project_id
        )
        
        print(f"✓ Retrieved {len(profiles)} profile topics")
        for profile in profiles:
            print(f"  - Topic: {profile.topic}")
            print(f"    Subtopics: {len(profile.subtopics)}")
            for subtopic_name, entry in list(profile.subtopics.items())[:2]:  # Show first 2
                content_preview = entry.content[:80] if len(entry.content) > 80 else entry.content
                print(f"      * {subtopic_name}: {content_preview}...")
        
        # Verify we got some profiles
        assert len(profiles) > 0, "Should extract at least one profile topic"
        print(f"\n✓ Memory extraction integration test passed\n")
    
    async def test_get_conversation_context(self, memobase, integration_config):
        """Test retrieving conversation context with LLM-based relevance filtering.
        
        This tests:
        1. Adding initial data
        2. Using LLM to filter relevant context for a conversation
        """
        user_id = f"test_context_{datetime.now().timestamp()}"
        project_id = "test_context_retrieval"
        
        print(f"\n{'='*80}")
        print(f"Test: Conversation Context Retrieval")
        print(f"User: {user_id}")
        print(f"{'='*80}\n")
        
        # First, add some data
        print("Step 1: Adding initial conversation data...")
        initial_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I'm a vegetarian and I love Italian food"),
                OpenAICompatibleMessage(role="assistant", content="Great! Do you have favorite Italian dishes?"),
                OpenAICompatibleMessage(role="user", content="I love pasta primavera and margherita pizza")
            ],
            type=BlobType.chat,
            created_at=datetime.now()
        )
        
        # Extract memories from initial conversation
        await memobase.extract_memories(
            user_id=user_id,
            blobs=[initial_blob],
            project_id=project_id
        )
        print("✓ Initial data extracted\n")
        
        # Now get context for a new conversation
        print("Step 2: Getting relevant context for new conversation...")
        new_conversation = [
            OpenAICompatibleMessage(role="user", content="Can you recommend a restaurant for dinner?")
        ]
        
        context = await memobase.get_conversation_context(
            user_id=user_id,
            conversation=new_conversation,
            max_token_size=1000
        )
        
        print(f"✓ Context retrieved")
        print(f"  Length: {len(context)} characters")
        context_preview = context[:200] if len(context) > 200 else context
        print(f"  Preview: {context_preview}...\n")
        
        assert context is not None
        assert len(context) > 0
        print(f"✓ Conversation context test passed\n")
    
    async def test_search_profiles_and_events(self, memobase, integration_config):
        """Test profile and event search functionality."""
        user_id = f"test_search_{datetime.now().timestamp()}"
        project_id = "test_search"
        
        print(f"\n{'='*80}")
        print(f"Test: Profile and Event Search")
        print(f"User: {user_id}")
        print(f"{'='*80}\n")
        
        # Add some searchable data
        print("Step 1: Adding searchable conversation data...")
        chat_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="I work as a software engineer in San Francisco"),
                OpenAICompatibleMessage(role="assistant", content="Interesting! What technologies do you work with?"),
                OpenAICompatibleMessage(role="user", content="Mainly Python and distributed systems. I enjoy working on database optimization.")
            ],
            type=BlobType.chat,
            created_at=datetime.now()
        )
        
        await memobase.extract_memories(
            user_id=user_id,
            blobs=[chat_blob],
            project_id=project_id
        )
        print("✓ Data extracted\n")
        
        # Search profiles
        print("Step 2: Searching profiles with query...")
        profiles = await memobase.search_profiles(
            user_id=user_id,
            query="What does the user do for work?",
            max_results=5
        )
        
        print(f"✓ Found {len(profiles)} relevant profile topics")
        for profile in profiles:
            print(f"  - {profile.topic}: {len(profile.subtopics)} subtopics")
        
        assert isinstance(profiles, list)
        print(f"\n✓ Profile search test passed\n")


@pytest.mark.skip
@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration handling."""
    
    def test_multiple_initialization_methods(self):
        """Test that different initialization methods work."""
        # Default initialization
        memobase1 = LindormMemobase.from_config(
            llm_api_key="key1",
            test_skip_persist=True
        )
        
        # From parameters
        memobase2 = LindormMemobase.from_config(
            language="zh",
            llm_api_key="key2",
            test_skip_persist=True
        )
        
        assert memobase1.config.language == "en"  # default
        assert memobase2.config.language == "zh"  # custom
