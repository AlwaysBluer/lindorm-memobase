# LindormMemobase API Reference

## Core Modules

### Configuration (`config.config`)

#### Config Class

Main configuration class for LindormMemobase with environment variable support.

```python
@dataclass
class Config:
    # Core settings
    persistent_chat_blobs: bool = False
    use_timezone: Optional[Literal["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Asia/Shanghai"]] = None
    
    # Buffer settings
    buffer_flush_interval: int = 60 * 60  # 1 hour
    max_chat_blob_buffer_token_size: int = 1024
    max_chat_blob_buffer_process_token_size: int = 16384
    max_profile_subtopics: int = 15
    max_pre_profile_token_size: int = 128
    
    # LLM settings
    language: Literal["en", "zh"] = "en"
    llm_style: Literal["openai", "doubao_cache"] = "openai"
    llm_base_url: str = None
    llm_api_key: str = None
    best_llm_model: str = "gpt-4o-mini"
    thinking_llm_model: str = "o4-mini"
    
    # Embedding settings
    enable_event_embedding: bool = True
    embedding_provider: Literal["openai", "jina"] = "openai"
    embedding_api_key: str = None
    embedding_base_url: str = None
    embedding_dim: int = 1536
    embedding_model: str = "text-embedding-3-small"
    
    # Profile settings
    profile_strict_mode: bool = False
    profile_validate_mode: bool = True
    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
```

**Methods:**
- `load_config() -> Config`: Load configuration from config.yaml and environment variables
- `timezone -> timezone`: Get configured timezone object

#### ProfileConfig Class

Project-specific profile configuration.

```python
@dataclass
class ProfileConfig:
    language: Literal["en", "zh"] = None
    profile_strict_mode: bool | None = None
    profile_validate_mode: bool | None = None
    additional_user_profiles: list[dict] = field(default_factory=list)
    overwrite_user_profiles: Optional[list[dict]] = None
    event_theme_requirement: Optional[str] = None
    event_tags: list[dict] = None
```

**Methods:**
- `load_config_string(config_string: str) -> ProfileConfig`: Load from YAML string

### Data Models (`core.models`)

#### Blob (`blob.py`)

Represents raw input data from users.

```python
@dataclass
class Blob:
    content: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    user_id: Optional[str] = None
    blob_type: str = "chat"
```

#### Profile Models (`profile.py`)

```python
@dataclass
class SubTopic:
    name: str
    description: Optional[str] = None
    update_description: Optional[str] = None
    validate_value: bool = False

@dataclass
class UserProfileTopic:
    topic: str
    description: Optional[str] = None
    sub_topics: list[SubTopic] = field(default_factory=list)
```

#### Response Models (`response.py`)

```python
class CODE(IntEnum):
    SUCCESS = 0
    INTERNAL_SERVER_ERROR = 500
    SERVER_PARSE_ERROR = 1001
    LLM_ERROR = 1002

@dataclass
class BaseResponse:
    errno: CODE = CODE.SUCCESS
    errmsg: str = ""
    data: Any = None

@dataclass
class ChatModalResponse:
    event_id: UUID
    add_profiles: list[str]
    update_profiles: list[str] 
    delete_profiles: list[str]
```

#### Type Definitions (`types.py`)

```python
FactResponse = TypedDict("FactResponse", {"topic": str, "sub_topic": str, "memo": str})
UpdateResponse = TypedDict("UpdateResponse", {"action": str, "memo": str})

Attributes = TypedDict("Attributes", {"topic": str, "sub_topic": str})
AddProfile = TypedDict("AddProfile", {"content": str, "attributes": Attributes})
UpdateProfile = TypedDict("UpdateProfile", {"profile_id": str, "content": str, "attributes": Attributes})

MergeAddResult = TypedDict("MergeAddResult", {
    "add": list[AddProfile],
    "update": list[UpdateProfile], 
    "delete": list[str],
    "update_delta": list[AddProfile],
})
```

### Extraction Pipeline (`core.extraction.processor`)

#### Main Processing (`process_blobs.py`)

```python
async def process_blobs(profile_config: ProfileConfig, blobs: list[Blob]) -> Promise[ChatModalResponse]:
    """
    Main blob processing pipeline.
    
    Args:
        profile_config: Project-specific configuration
        blobs: List of user input blobs to process
        
    Returns:
        Promise containing processing results
        
    Pipeline:
    1. Truncate blobs to fit token limits
    2. Generate entry summary
    3. Extract topics and process events in parallel
    4. Return structured response
    """
```

```python
def truncate_chat_blobs(blobs: list[Blob], max_token_size: int) -> tuple[list[str], list[Blob]]:
    """
    Truncate blob list to fit within token limits.
    
    Args:
        blobs: Input blobs (processed in reverse chronological order)
        max_token_size: Maximum total token count
        
    Returns:
        Truncated blob list in chronological order
    """
```

#### Topic Extraction (`extract.py`)

```python
async def extract_topics(user_memo: str, project_profiles: ProfileConfig) -> Promise[dict]:
    """
    Extract structured topics from user conversation.
    
    Args:
        user_memo: Summarized user conversation
        project_profiles: Profile configuration for extraction
        
    Returns:
        Promise containing:
        - fact_contents: List of extracted fact descriptions
        - fact_attributes: List of corresponding topic/subtopic attributes
        - total_profiles: Available profile slots
        
    Features:
    - Supports strict mode for controlled extraction
    - Validates against predefined topic/subtopic schemas
    - Merges facts by topic-subtopic pairs
    - Filters invalid extractions
    """
```

```python
def merge_by_topic_sub_topics(new_facts: list[FactResponse]) -> list[FactResponse]:
    """
    Merge facts with same topic-subtopic combination.
    
    Args:
        new_facts: List of extracted facts
        
    Returns:
        Deduplicated facts with merged memos
    """
```

#### Profile Merging (`merge.py`)

```python
async def merge_or_valid_new_memos(
    fact_contents: list[str],
    fact_attributes: list[dict], 
    config: ProfileConfig,
    total_profiles: list[UserProfileTopic],
) -> Promise[MergeAddResult]:
    """
    Merge new facts with existing profiles.
    
    Args:
        fact_contents: List of fact descriptions
        fact_attributes: Corresponding topic/subtopic attributes
        config: Profile configuration
        total_profiles: Available profile definitions
        
    Returns:
        Promise containing merge results:
        - add: New profiles to create
        - update: Existing profiles to update
        - delete: Profiles to remove
        - update_delta: Change tracking
        
    Processing:
    - Validates new facts against existing profiles using LLM
    - Supports UPDATE, APPEND, and ABORT actions
    - Tracks update frequency
    - Handles profile validation mode
    """
```

```python
async def handle_profile_merge_or_valid(
    profile_attributes: dict,
    profile_content: str,
    config: ProfileConfig,
    profile_runtime_maps: dict[tuple[str, str], ProfileData],
    profile_define_maps: dict[tuple[str, str], SubTopic], 
    session_merge_validate_results: MergeAddResult,
) -> Promise[None]:
    """
    Handle individual profile merge or validation.
    
    Args:
        profile_attributes: Topic and subtopic information
        profile_content: New fact content
        config: Profile configuration
        profile_runtime_maps: Existing runtime profiles
        profile_define_maps: Profile definitions
        session_merge_validate_results: Accumulator for results
        
    Actions:
    - UPDATE: Replace existing profile content
    - APPEND: Add to existing profile content  
    - ABORT: Reject invalid content
    """
```

### LLM Integration (`llm`)

#### Completion Interface (`complete.py`)

```python
async def llm_complete(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    **kwargs
) -> Promise[str]:
    """
    Generic LLM completion interface.
    
    Args:
        prompt: User prompt
        system_prompt: System instructions
        temperature: Sampling temperature
        **kwargs: Provider-specific parameters
        
    Returns:
        Promise containing LLM response
        
    Supports:
    - Multiple LLM providers
    - Error handling and retries
    - Token counting and optimization
    """
```

#### OpenAI Provider (`openai_model_llm.py`)

```python
class OpenAIModelLLM:
    def __init__(self, config: Config):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url
        )
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """OpenAI-compatible completion."""
```

### Embedding System (`embedding`)

#### OpenAI Embeddings (`openai_embedding.py`)

```python
class OpenAIEmbedding:
    def __init__(self, config: Config):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url
        )
    
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings for text."""
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
```

#### Jina Embeddings (`jina_embedding.py`)

```python
class JinaEmbedding:
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.embedding_base_url or "https://api.jina.ai/v1"
    
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using Jina API."""
```

### Utility Functions (`utils`)

#### Promise System (`promise.py`)

```python
@dataclass
class Promise(Generic[D]):
    """Promise-based async error handling."""
    
    @classmethod
    def resolve(cls, data: D) -> "Promise[D]":
        """Create successful promise."""
    
    @classmethod  
    def reject(cls, errcode: CODE, errmsg: str) -> "Promise":
        """Create failed promise."""
    
    def ok(self) -> bool:
        """Check if promise succeeded."""
    
    def data(self) -> Optional[D]:
        """Get promise data (raises on failure)."""
    
    def code(self) -> CODE:
        """Get error code."""
    
    def msg(self) -> str:
        """Get error message."""
    
    def to_response(self, ResponseModel: Type[T]) -> T:
        """Convert to response model."""
```

#### Tools (`tools.py`)

```python
def get_blob_str(blob: Blob) -> str:
    """Extract string content from blob."""

def get_encoded_tokens(text: str) -> list[int]:
    """Get token encoding for text."""

def CODE -> IntEnum:
    """Error code definitions."""
```

### Constants (`core.constants`)

```python
class ContanstTable:
    """Field name constants."""
    topic = "topic"
    sub_topic = "sub_topic" 
    memo = "memo"
    update_hits = "update_hits"
    roleplay_plot_status = "roleplay_plot_status"

class BufferStatus:
    """Buffer processing status."""
    idle = "idle"
    processing = "processing"
    done = "done"
    failed = "failed"
```

## Usage Examples

### Basic Setup

```python
from config.config import Config, ProfileConfig
from core.extraction.processor.process_blobs import process_blobs
from core.models.blob import Blob
from datetime import datetime

# Load configuration
config = Config.load_config()

# Create profile configuration
profile_config = ProfileConfig(
    language="en",
    profile_strict_mode=True,
    additional_user_profiles=[
        {
            "topic": "interests",
            "description": "User interests and hobbies",
            "sub_topics": [
                {
                    "name": "music",
                    "description": "Musical preferences and activities"
                }
            ]
        }
    ]
)

# Create sample blobs
blobs = [
    Blob(
        content="I love listening to jazz music", 
        timestamp=datetime.now(),
        user_id="user123"
    ),
    Blob(
        content="I play piano in my free time",
        timestamp=datetime.now(), 
        user_id="user123"
    )
]

# Process blobs
result = await process_blobs(profile_config, blobs)
if result.ok():
    response = result.data()
    print(f"Added {len(response.add_profiles)} profiles")
    print(f"Updated {len(response.update_profiles)} profiles")
else:
    print(f"Processing failed: {result.msg()}")
```

### Custom LLM Provider

```python
from llm.complete import LLMProvider
from abc import ABC, abstractmethod

class CustomLLMProvider(LLMProvider):
    async def complete(self, prompt: str, **kwargs) -> str:
        # Custom implementation
        return "Custom response"

# Register provider
config.llm_style = "custom"
```

### Configuration with Environment Variables

```bash
# Set environment variables
export MEMOBASE_LLM_API_KEY="your-api-key"
export MEMOBASE_LLM_BASE_URL="https://api.openai.com/v1"
export MEMOBASE_LANGUAGE="en"
export MEMOBASE_PROFILE_STRICT_MODE="true"
```

```python
# Configuration automatically loads from environment
config = Config.load_config()
```

### Error Handling

```python
from models.promise import Promise, CODE
from utils.errors import MemobaseError

async def safe_processing():
    try:
        result = await process_blobs(profile_config, blobs)
        if not result.ok():
            if result.code() == CODE.LLM_ERROR:
                print("LLM service unavailable")
            elif result.code() == CODE.SERVER_PARSE_ERROR:
                print("Failed to parse LLM response")
            else:
                print(f"Unknown error: {result.msg()}")
        return result
    except Exception as e:
        print(f"Unexpected error: {e}")
        return Promise.reject(CODE.INTERNAL_SERVER_ERROR, str(e))
```

## Configuration Reference

### Required Configuration

```yaml
# config.yaml
llm_api_key: "your-openai-api-key"
best_llm_model: "gpt-4o-mini"
language: "en"

# Optional embedding configuration
enable_event_embedding: true
embedding_provider: "openai"
embedding_api_key: "your-embedding-api-key"
embedding_model: "text-embedding-3-small"
```

### Environment Variables

All configuration fields can be overridden with environment variables using the pattern `MEMOBASE_{FIELD_NAME}`:

- `MEMOBASE_LLM_API_KEY`
- `MEMOBASE_LLM_BASE_URL`  
- `MEMOBASE_LANGUAGE`
- `MEMOBASE_PROFILE_STRICT_MODE`
- `MEMOBASE_EMBEDDING_API_KEY`
- etc.

### Profile Configuration

```yaml
# Project-specific profile configuration
language: "en"
profile_strict_mode: true
profile_validate_mode: true

additional_user_profiles:
  - topic: "interests"
    description: "User interests and hobbies"
    sub_topics:
      - name: "music"
        description: "Musical preferences"
        validate_value: true
      - name: "sports" 
        description: "Sports activities"

event_theme_requirement: "Focus on user information, not instructions"
```

This API reference provides comprehensive documentation for integrating and extending LindormMemobase functionality.