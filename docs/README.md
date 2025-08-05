# LindormMemobase Documentation

A lightweight memory extraction and profile management system for LLM applications.

## Overview

LindormMemobase is a simplified version of the Memobase memory system, designed for local deployment and testing. It implements core memory extraction and profile management functionality without the full server infrastructure.

## Table of Contents

1. **[Quick Start Guide](quickstart.md)** - Get up and running quickly
2. **[Architecture Documentation](architecture.md)** - Understand the system design
3. **[API Reference](api_reference.md)** - Complete API documentation
4. **[Issues and Improvements](issues_and_improvements.md)** - Known issues and recommended fixes

## Features

- 🧠 **Memory Extraction**: Extract structured information from user conversations
- 🏷️ **Profile Management**: Organize user information into topic-based profiles
- 🌍 **Multi-language Support**: English and Chinese language processing
- 🔌 **LLM Integration**: Support for OpenAI and compatible APIs
- 📊 **Embedding Support**: Vector embeddings for semantic search
- ⚙️ **Configurable**: Flexible configuration system with environment variable support

## Quick Example

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
        additional_user_profiles=[
            {
                "topic": "interests",
                "description": "User interests and hobbies",
                "sub_topics": [
                    {"name": "music", "description": "Musical preferences"}
                ]
            }
        ]
    )
    
    # Create conversation blobs
    blobs = [
        Blob(content="I love playing jazz piano", timestamp=datetime.now())
    ]
    
    # Process the conversation
    result = await process_blobs(profile_config, blobs)
    
    if result.ok():
        response = result.data()
        print(f"Extracted {len(response.add_profiles)} profiles")
    else:
        print(f"Error: {result.msg()}")

asyncio.run(main())
```

## Installation

1. **Install dependencies:**
   ```bash
   cd lindormmemobase
   uv sync
   ```

2. **Set up configuration:**
   ```bash
   export MEMOBASE_LLM_API_KEY=your-openai-api-key
   ```

3. **Run the example:**
   ```bash
   python your_script.py
   ```

## Core Concepts

### Blobs
Raw input data from users, typically chat messages or documents.

### Profiles
Structured user information organized by topics and subtopics.

### Extraction Pipeline
1. **Summarization**: Convert blobs to coherent summary
2. **Extraction**: Extract structured facts from summary  
3. **Merging**: Merge facts with existing profiles
4. **Organization**: Optimize profile structure

### Configuration
- **Global Config**: System-wide settings (LLM, embedding, limits)
- **Profile Config**: Project-specific profile definitions
- **Environment Variables**: Override any configuration setting

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     Blobs       │───▶│  Extraction      │───▶│    Profiles     │
│ (Raw messages)  │    │   Pipeline       │    │ (Structured)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   LLM Provider   │
                    │ (OpenAI/Doubao)  │
                    └──────────────────┘
```

## Next Steps

- **Quick Start**: Follow the [Quick Start Guide](quickstart.md) for immediate setup
- **Deep Dive**: Read the [Architecture Documentation](architecture.md) for system understanding
- **API Usage**: Check the [API Reference](api_reference.md) for detailed integration
- **Issues**: Review [Issues and Improvements](issues_and_improvements.md) for current limitations

## Contributing

LindormMemobase is part of the larger Memobase project. For contributions:

1. Review the issues documentation for known problems
2. Follow the existing code patterns and conventions
3. Add tests for new functionality
4. Update documentation for API changes

## License

Apache 2.0 License - see the main Memobase project for details.

## Support

For questions and support:
- Check the documentation in this directory
- Review the main Memobase project README
- File issues in the main repository