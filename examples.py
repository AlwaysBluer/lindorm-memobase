"""
MiniMemobase Usage Examples
Complete guide on how to use MiniMemobase as a Python package
"""

# =============================================================================
# Example 1: Basic Setup and Configuration
# =============================================================================

from config import Config
from api import MiniMemobase, create_config
from models.blob import Blob, BlobType
from models.profile_topic import ProfileConfig
import asyncio

async def basic_usage_example():
    """Basic usage example showing configuration and initialization"""
    
    print("=== Example 1: Basic Setup ===")
    
    # Method 1: Load config from files (recommended)
    config = Config.load_config()  # Loads from config.yaml and .env
    print(f"Loaded config: language={config.language}, model={config.best_llm_model}")
    
    # Method 2: Create custom config with overrides
    custom_config = create_config(
        language="en",
        llm_api_key="your-openai-api-key-here",
        best_llm_model="gpt-4o-mini",
        max_chat_blob_buffer_process_token_size=8192,
        llm_style="openai"
    )
    print(f"Custom config: {custom_config.language}, {custom_config.best_llm_model}")
    
    # Initialize MiniMemobase with your config
    memobase = MiniMemobase(config=custom_config)
    print("✅ MiniMemobase initialized successfully!")
    
    return memobase, custom_config


# =============================================================================
# Example 2: Processing User Data
# =============================================================================

async def data_processing_example():
    """Example showing how to process user conversations and extract memories"""
    
    print("\n=== Example 2: Processing User Data ===")
    
    # Initialize MiniMemobase
    config = create_config(
        language="en",
        llm_api_key="your-api-key",  # Replace with real API key
        best_llm_model="gpt-4o-mini"
    )
    memobase = MiniMemobase(config=config)
    
    # Create user data blobs (conversations, documents, etc.)
    user_blobs = [
        Blob(
            type=BlobType.chat,
            fields={
                "messages": [
                    {"role": "user", "content": "Hi, I'm John, 25 years old, working as a software engineer at Google"},
                    {"role": "assistant", "content": "Nice to meet you John! Tell me more about your work."},
                    {"role": "user", "content": "I love programming in Python and working on AI projects. I'm originally from California but now live in New York."}
                ]
            }
        ),
        Blob(
            type=BlobType.chat,
            fields={
                "messages": [
                    {"role": "user", "content": "I'm planning to learn machine learning this year and maybe get a promotion"},
                    {"role": "assistant", "content": "That sounds like great goals!"},
                    {"role": "user", "content": "Yeah, I'm particularly interested in NLP and want to work on language models"}
                ]
            }
        )
    ]
    
    # Create profile configuration (optional customization)
    profile_config = ProfileConfig(
        language="en",
        profile_strict_mode=False,  # Allow flexible profile extraction
    )
    
    # Process the user data to extract memories and build profile
    user_id = "john_doe_123"
    
    try:
        # This would extract structured information from the conversations
        # Note: This requires a valid LLM API key to work
        print("Processing user blobs... (would need valid API key)")
        # result = await memobase.process_user_blobs(user_id, user_blobs, profile_config)
        # print(f"Processing result: {result}")
        
        print("✅ Data processing setup complete!")
        
    except Exception as e:
        print(f"⚠️  Processing failed (expected without valid API key): {e}")
    
    return user_blobs, profile_config


# =============================================================================
# Example 3: Configuration Customization
# =============================================================================

def configuration_examples():
    """Examples of different configuration options"""
    
    print("\n=== Example 3: Configuration Options ===")
    
    # English configuration
    english_config = create_config(
        language="en",
        llm_api_key="your-openai-key",
        best_llm_model="gpt-4o",
        thinking_llm_model="o1-mini",
        summary_llm_model="gpt-4o-mini",
        max_profile_subtopics=10,
        llm_style="openai"
    )
    
    # Chinese configuration
    chinese_config = create_config(
        language="zh", 
        llm_api_key="your-api-key",
        best_llm_model="qwen-max-latest",
        llm_style="doubao_cache",  # Use ByteDance Doubao with caching
        llm_base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    
    # Advanced configuration with embeddings
    advanced_config = create_config(
        language="en",
        llm_api_key="your-openai-key",
        embedding_provider="jina",  # or "openai"
        embedding_api_key="your-jina-key",
        embedding_base_url="https://api.jina.ai/v1",
        embedding_model="jina-embeddings-v3",
        max_chat_blob_buffer_process_token_size=16384,
        use_timezone="America/New_York"
    )
    
    print("✅ Multiple configuration examples created!")
    
    return english_config, chinese_config, advanced_config


# =============================================================================
# Example 4: Custom Profile Configuration
# =============================================================================

def profile_configuration_examples():
    """Examples of customizing user profile extraction"""
    
    print("\n=== Example 4: Profile Configuration ===")
    
    # Basic profile config
    basic_profile = ProfileConfig(
        language="en",
        profile_strict_mode=False,
        profile_validate_mode=True
    )
    
    # Custom profile with additional topics
    custom_profile = ProfileConfig(
        language="en",
        additional_user_profiles=[
            {
                "topic": "programming_skills",
                "description": "User's programming languages and technical skills",
                "sub_topics": ["languages", "frameworks", "tools", "experience_years"]
            },
            {
                "topic": "career_goals", 
                "description": "User's career aspirations and professional development goals",
                "sub_topics": ["short_term_goals", "long_term_goals", "desired_companies", "salary_expectations"]
            }
        ],
        event_tags=[
            {
                "name": "mood",
                "description": "User's current emotional state"
            },
            {
                "name": "activity",
                "description": "What the user is currently doing"
            }
        ]
    )
    
    print("✅ Profile configurations created!")
    
    return basic_profile, custom_profile


# =============================================================================
# Example 5: Standalone Functions Usage
# =============================================================================

async def standalone_functions_example():
    """Example using individual functions instead of MiniMemobase class"""
    
    print("\n=== Example 5: Using Standalone Functions ===")
    
    from api import extract_memories
    
    # Create test data
    config = create_config(
        language="en",
        llm_api_key="your-api-key",
        best_llm_model="gpt-4o-mini"
    )
    
    test_blobs = [
        Blob(
            type=BlobType.chat,
            fields={"content": "I'm learning to play guitar and love rock music"}
        )
    ]
    
    try:
        # Use standalone function
        result = await extract_memories(
            user_id="test_user",
            blobs=test_blobs,
            config=config
        )
        print(f"✅ Standalone function result: {result}")
        
    except Exception as e:
        print(f"⚠️  Standalone function failed (expected without API key): {e}")


# =============================================================================
# Example 6: Production-Ready Usage Pattern
# =============================================================================

class UserMemoryManager:
    """Production-ready wrapper for MiniMemobase"""
    
    def __init__(self, api_key: str, language: str = "en"):
        self.config = create_config(
            language=language,
            llm_api_key=api_key,
            best_llm_model="gpt-4o-mini",
            max_chat_blob_buffer_process_token_size=8192,
            profile_strict_mode=False
        )
        self.memobase = MiniMemobase(config=self.config)
        self.profile_config = ProfileConfig(language=language)
    
    async def add_conversation(self, user_id: str, messages: list[dict]):
        """Add a conversation to user's memory"""
        blob = Blob(
            type=BlobType.chat,
            fields={"messages": messages}
        )
        
        try:
            result = await self.memobase.process_user_blobs(
                user_id=user_id,
                blobs=[blob],
                profile_config=self.profile_config
            )
            return result
            
        except Exception as e:
            print(f"Error processing conversation: {e}")
            return None
    
    async def add_document(self, user_id: str, content: str, title: str = None):
        """Add a document to user's memory"""
        blob = Blob(
            type=BlobType.doc,
            fields={
                "content": content,
                "title": title or "Untitled Document"
            }
        )
        
        try:
            result = await self.memobase.process_user_blobs(
                user_id=user_id,
                blobs=[blob], 
                profile_config=self.profile_config
            )
            return result
            
        except Exception as e:
            print(f"Error processing document: {e}")
            return None


async def production_example():
    """Production usage example"""
    
    print("\n=== Example 6: Production Usage ===")
    
    # Initialize memory manager
    # memory_manager = UserMemoryManager(
    #     api_key="your-real-api-key-here",
    #     language="en"
    # )
    
    # # Process user conversation
    # conversation = [
    #     {"role": "user", "content": "I just got promoted to Senior Engineer!"},
    #     {"role": "assistant", "content": "Congratulations! Tell me more about it."},
    #     {"role": "user", "content": "I'll be leading a team of 5 developers on a new AI project."}
    # ]
    
    # result = await memory_manager.add_conversation("user123", conversation)
    # print(f"Conversation processed: {result}")
    
    print("✅ Production example structure ready!")


# =============================================================================
# Main Demo Function
# =============================================================================

async def main():
    """Run all examples"""
    
    print("MiniMemobase Usage Examples")
    print("=" * 50)
    
    # Run all examples
    await basic_usage_example()
    await data_processing_example() 
    configuration_examples()
    profile_configuration_examples()
    await standalone_functions_example()
    await production_example()
    
    print("\n" + "=" * 50)
    print("🎉 All examples completed!")
    print("\nTo use MiniMemobase in production:")
    print("1. Set up your .env file with API keys")
    print("2. Configure config.yaml with your preferences") 
    print("3. Use the UserMemoryManager class or MiniMemobase directly")
    print("4. Process user data with process_user_blobs()")


if __name__ == "__main__":
    asyncio.run(main())