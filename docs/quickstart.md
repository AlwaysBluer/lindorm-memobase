# LindormMemobase Quick Start Guide

## Installation

### Prerequisites

- Python 3.12 or higher
- OpenAI API key (or compatible LLM provider)

### Setup

1. **Clone or navigate to the lindormmemobase directory:**
   ```bash
   cd lindormmemobase
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   # or with pip:
   pip install -e .
   ```

3. **Create configuration file:**
   ```bash
   cp config.yaml.example config.yaml
   ```

4. **Set up environment variables:**
   ```bash
   # Create .env file
   echo "MEMOBASE_LLM_API_KEY=your-openai-api-key" > .env
   echo "MEMOBASE_EMBEDDING_API_KEY=your-openai-api-key" >> .env
   ```

## Basic Configuration

### Minimal config.yaml

```yaml
# Basic LLM configuration
llm_api_key: null  # Set via environment variable
best_llm_model: "gpt-4o-mini"
thinking_llm_model: "gpt-4o-mini"
language: "en"

# Profile settings
profile_strict_mode: false
profile_validate_mode: true

# Embedding settings (optional)
enable_event_embedding: true
embedding_provider: "openai"
embedding_model: "text-embedding-3-small"

# Token limits
max_chat_blob_buffer_token_size: 1024
max_chat_blob_buffer_process_token_size: 16384
```

### Environment Variables

```bash
# Required
MEMOBASE_LLM_API_KEY=sk-your-openai-api-key

# Optional
MEMOBASE_LLM_BASE_URL=https://api.openai.com/v1
MEMOBASE_EMBEDDING_API_KEY=sk-your-embedding-key
MEMOBASE_LANGUAGE=en
```

## Quick Example

### Basic Usage

```python
import asyncio
from datetime import datetime
from config.config import Config, ProfileConfig
from core.extraction.processor.process_blobs import process_blobs
from core.models.blob import Blob

async def main():
    # Load configuration
    config = Config.load_config()
    
    # Create profile configuration
    profile_config = ProfileConfig(
        language="en",
        profile_strict_mode=False,
        additional_user_profiles=[
            {
                "topic": "personal_info",
                "description": "Basic personal information",
                "sub_topics": [
                    {
                        "name": "interests",
                        "description": "Hobbies and interests"
                    },
                    {
                        "name": "preferences", 
                        "description": "User preferences"
                    }
                ]
            }
        ]
    )
    
    # Create sample conversation blobs
    blobs = [
        Blob(
            content="Hi, I'm John and I love playing guitar",
            timestamp=datetime.now(),
            user_id="user_123"
        ),
        Blob(
            content="I've been learning jazz for 3 years",
            timestamp=datetime.now(),
            user_id="user_123"
        ),
        Blob(
            content="I also enjoy reading science fiction books",
            timestamp=datetime.now(),
            user_id="user_123"
        )
    ]
    
    # Process the blobs
    print("Processing user conversation...")
    result = await process_blobs(profile_config, blobs)
    
    if result.ok():
        response = result.data()
        print(f"✅ Processing successful!")
        print(f"📝 Added profiles: {len(response.add_profiles)}")
        print(f"🔄 Updated profiles: {len(response.update_profiles)}")
        print(f"🗑️ Deleted profiles: {len(response.delete_profiles)}")
        print(f"🆔 Event ID: {response.event_id}")
    else:
        print(f"❌ Processing failed: {result.msg()}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Running the Example

```bash
python quick_start_example.py
```

Expected output:
```
Processing user conversation...
✅ Processing successful!
📝 Added profiles: 2
🔄 Updated profiles: 0
🗑️ Deleted profiles: 0
🆔 Event ID: 12345678-1234-5678-9012-123456789abc
```

## Step-by-Step Tutorial

### 1. Understanding Blobs

Blobs represent raw user input data:

```python
from core.models.blob import Blob
from datetime import datetime

# Create a blob from user message
blob = Blob(
    content="I love cooking Italian food",
    timestamp=datetime.now(),
    user_id="user_123",
    metadata={"source": "chat", "channel": "web"}
)
```

### 2. Configuring Profiles

Profiles define what information to extract:

```python
profile_config = ProfileConfig(
    language="en",
    profile_strict_mode=True,  # Only extract predefined topics
    additional_user_profiles=[
        {
            "topic": "food_preferences",
            "description": "User's food and cooking preferences",
            "sub_topics": [
                {
                    "name": "cuisine_types",
                    "description": "Preferred cuisine types",
                    "validate_value": True  # Validate with LLM
                },
                {
                    "name": "cooking_skills",
                    "description": "Cooking abilities and experience"
                }
            ]
        }
    ]
)
```

### 3. Processing Pipeline

The processing pipeline:

1. **Summarization**: Converts multiple blobs into coherent summary
2. **Extraction**: Extracts structured facts from summary
3. **Merging**: Merges new facts with existing profiles
4. **Organization**: Organizes and optimizes profile structure

```python
# The process_blobs function handles the entire pipeline
result = await process_blobs(profile_config, blobs)
```

### 4. Handling Results

```python
if result.ok():
    response = result.data()
    
    # Process successful results
    for profile_id in response.add_profiles:
        print(f"New profile created: {profile_id}")
    
    for profile_id in response.update_profiles:
        print(f"Profile updated: {profile_id}")
        
else:
    # Handle errors
    error_code = result.code()
    error_message = result.msg()
    print(f"Error {error_code}: {error_message}")
```

## Advanced Configuration

### Multiple Languages

```python
# English configuration
en_config = ProfileConfig(
    language="en",
    additional_user_profiles=[
        {
            "topic": "interests",
            "description": "User interests and hobbies",
            "sub_topics": [{"name": "music", "description": "Musical preferences"}]
        }
    ]
)

# Chinese configuration  
zh_config = ProfileConfig(
    language="zh",
    additional_user_profiles=[
        {
            "topic": "兴趣爱好",
            "description": "用户的兴趣和爱好",
            "sub_topics": [{"name": "音乐", "description": "音乐偏好"}]
        }
    ]
)
```

### Custom LLM Providers

```python
# Using a custom OpenAI-compatible endpoint
custom_config = Config(
    llm_api_key="your-api-key",
    llm_base_url="https://your-custom-endpoint.com/v1",
    best_llm_model="custom-model-name",
    language="en"
)
```

### Embedding Configuration

```python
# Using Jina embeddings
jina_config = Config(
    enable_event_embedding=True,
    embedding_provider="jina",
    embedding_api_key="your-jina-key",
    embedding_model="jina-embeddings-v3",
    embedding_dim=1024
)
```

## Common Use Cases

### 1. Chat Application

```python
async def process_chat_message(user_id: str, message: str):
    blob = Blob(
        content=message,
        timestamp=datetime.now(),
        user_id=user_id,
        metadata={"type": "chat_message"}
    )
    
    # Simple profile for chat applications
    chat_config = ProfileConfig(
        language="en",
        profile_strict_mode=False,  # Allow free-form extraction
        additional_user_profiles=[
            {
                "topic": "user_context",
                "description": "General user information from chat",
                "sub_topics": [
                    {"name": "personal", "description": "Personal information"},
                    {"name": "preferences", "description": "User preferences"},
                    {"name": "current_context", "description": "Current conversation context"}
                ]
            }
        ]
    )
    
    return await process_blobs(chat_config, [blob])
```

### 2. Customer Support

```python
async def process_support_conversation(conversation_history: list[str], customer_id: str):
    blobs = [
        Blob(
            content=message,
            timestamp=datetime.now(),
            user_id=customer_id,
            metadata={"type": "support_message"}
        )
        for message in conversation_history
    ]
    
    support_config = ProfileConfig(
        language="en",
        profile_strict_mode=True,
        additional_user_profiles=[
            {
                "topic": "customer_profile",
                "description": "Customer information for support",
                "sub_topics": [
                    {"name": "issues", "description": "Customer issues and problems"},
                    {"name": "product_usage", "description": "How customer uses products"},
                    {"name": "satisfaction", "description": "Customer satisfaction indicators"}
                ]
            }
        ]
    )
    
    return await process_blobs(support_config, blobs)
```

### 3. Educational Assistant

```python
async def process_learning_session(student_id: str, session_messages: list[str]):
    blobs = [
        Blob(
            content=msg,
            timestamp=datetime.now(),
            user_id=student_id,
            metadata={"type": "learning_session"}
        )
        for msg in session_messages
    ]
    
    education_config = ProfileConfig(
        language="en",
        profile_strict_mode=True,
        additional_user_profiles=[
            {
                "topic": "learning_profile",
                "description": "Student learning characteristics",
                "sub_topics": [
                    {"name": "strengths", "description": "Academic strengths"},
                    {"name": "difficulties", "description": "Learning difficulties"},
                    {"name": "interests", "description": "Subject interests"},
                    {"name": "learning_style", "description": "Preferred learning style"}
                ]
            }
        ]
    )
    
    return await process_blobs(education_config, blobs)
```

## Troubleshooting

### Common Issues

#### 1. "llm_api_key is required" Error

```bash
# Make sure API key is set
export MEMOBASE_LLM_API_KEY=your-api-key
# or set in config.yaml
llm_api_key: "your-api-key"
```

#### 2. Import Errors

```python
# Fix import paths in your code
from core.models.blob import Blob  # Correct
# not: from models.blob import Blob
```

#### 3. Token Limit Exceeded

```yaml
# Increase token limits in config.yaml
max_chat_blob_buffer_process_token_size: 32768  # Increase from default 16384
```

#### 4. LLM Response Parsing Errors

```python
# Enable debug logging
import logging
logging.getLogger("memobase_server").setLevel(logging.DEBUG)
```

### Debug Mode

```python
from config.config import LOG
import logging

# Enable detailed logging
LOG.setLevel(logging.DEBUG)

# Add file logging
file_handler = logging.FileHandler('lindormmemobase.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
LOG.addHandler(file_handler)
```

### Performance Tips

1. **Batch Processing**: Process multiple blobs together when possible
2. **Token Management**: Monitor token usage and adjust limits
3. **Profile Optimization**: Use strict mode to control extraction scope
4. **Caching**: Implement caching for frequently accessed profiles

### Next Steps

1. **Explore the full API**: Check `docs/api_reference.md`
2. **Review architecture**: Read `docs/architecture.md`
3. **Check issues**: See `docs/issues_and_improvements.md` for known issues
4. **Extend functionality**: Add custom LLM providers or embedding models
5. **Production deployment**: Implement proper error handling and monitoring

## Example Projects

### Complete Chat Bot Integration

```python
import asyncio
from datetime import datetime
from typing import List
from config.config import Config, ProfileConfig
from core.extraction.processor.process_blobs import process_blobs
from core.models.blob import Blob

class LindormMemobaseChat:
    def __init__(self):
        self.config = Config.load_config()
        self.profile_config = ProfileConfig(
            language="en",
            profile_strict_mode=False,
            additional_user_profiles=[
                {
                    "topic": "user_profile",
                    "description": "User information from chat",
                    "sub_topics": [
                        {"name": "personal", "description": "Personal details"},
                        {"name": "preferences", "description": "User preferences"},
                        {"name": "context", "description": "Current conversation context"}
                    ]
                }
            ]
        )
        self.conversation_history = {}
    
    async def process_message(self, user_id: str, message: str) -> dict:
        """Process a new chat message and update user profile."""
        
        # Add to conversation history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        self.conversation_history[user_id].append(message)
        
        # Create blob for current message
        blob = Blob(
            content=message,
            timestamp=datetime.now(),
            user_id=user_id
        )
        
        # Process the message
        result = await process_blobs(self.profile_config, [blob])
        
        if result.ok():
            response = result.data()
            return {
                "success": True,
                "profiles_added": len(response.add_profiles),
                "profiles_updated": len(response.update_profiles),
                "event_id": str(response.event_id)
            }
        else:
            return {
                "success": False,
                "error": result.msg()
            }
    
    async def get_user_summary(self, user_id: str) -> dict:
        """Get a summary of what we know about the user."""
        # This would typically query a database
        # For now, return conversation history length
        history_length = len(self.conversation_history.get(user_id, []))
        return {
            "user_id": user_id,
            "conversation_messages": history_length,
            "last_activity": datetime.now().isoformat()
        }

# Usage example
async def main():
    chat_bot = LindormMemobaseChat()
    
    # Simulate conversation
    user_id = "user_123"
    messages = [
        "Hi, I'm Sarah and I love programming",
        "I work as a software engineer at a tech startup",
        "My favorite programming language is Python",
        "I'm also learning machine learning in my free time"
    ]
    
    for message in messages:
        print(f"Processing: {message}")
        result = await chat_bot.process_message(user_id, message)
        print(f"Result: {result}")
        print("---")
    
    # Get user summary
    summary = await chat_bot.get_user_summary(user_id)
    print(f"User summary: {summary}")

if __name__ == "__main__":
    asyncio.run(main())
```

This quick start guide provides everything needed to begin using LindormMemobase for memory extraction and profile management in your applications.