# LindormMemobase Architecture Documentation

## Overview

LindormMemobase is a lightweight version of the Memobase memory system, designed for local deployment and testing. It implements the core memory extraction and profile management functionality without the full server infrastructure.

## Project Structure

```
lindormmemobase/
├── config/                 # Configuration management
│   ├── __init__.py
│   └── config.py           # Config classes and environment loading
├── core/                   # Core business logic
│   ├── buffer/             # Buffer management (empty - needs implementation)
│   ├── extraction/         # Memory extraction pipeline
│   │   ├── processor/      # Processing logic
│   │   │   ├── extract.py  # Topic extraction from user input
│   │   │   ├── merge.py    # Profile merging and validation
│   │   │   ├── organize.py # Profile organization
│   │   │   ├── process_blobs.py # Main blob processing pipeline
│   │   │   └── ...
│   │   └── prompts/        # LLM prompts and templates
│   ├── models/             # Data models and types
│   │   ├── blob.py        # Blob data structures
│   │   ├── profile.py     # Profile data structures  
│   │   ├── response.py    # Response models
│   │   └── types.py       # Type definitions
│   └── search/            # Search functionality (empty - needs implementation)
├── embedding/             # Embedding providers
│   ├── jina_embedding.py  # Jina AI embeddings
│   └── openai_embedding.py # OpenAI embeddings
├── llm/                   # LLM providers
│   ├── complete.py        # LLM completion interface
│   └── openai_model_llm.py # OpenAI LLM implementation
├── utils/                 # Utility functions
│   ├── errors.py          # Error definitions
│   ├── promise.py         # Promise-based async handling
│   └── tools.py           # Helper functions
└── main.py               # Main entry point (empty)
```

## Core Components

### 1. Memory Extraction Pipeline

The core extraction logic follows this flow:

1. **Blob Processing** (`process_blobs.py`):
   - Truncates chat blobs to fit token limits
   - Generates entry summary from raw blobs
   - Processes profiles and events in parallel
   
2. **Topic Extraction** (`extract.py`):
   - Extracts structured facts from user conversations
   - Validates against predefined topic/subtopic schemas
   - Supports strict mode for controlled extraction

3. **Profile Merging** (`merge.py`):
   - Merges new facts with existing profiles
   - Validates profile updates using LLM
   - Handles UPDATE, APPEND, and ABORT actions

4. **Profile Organization** (`organize.py`):
   - Organizes profiles by relevance and importance
   - Manages profile limits and cleanup

### 2. Configuration System

The configuration system supports:
- YAML-based configuration files
- Environment variable overrides
- Type-safe configuration loading
- Project-specific profile configurations

Key configuration classes:
- `Config`: Global system configuration
- `ProfileConfig`: Project-specific profile settings

### 3. LLM Integration

Supports multiple LLM providers:
- OpenAI API compatible endpoints
- Doubao (ByteDance) with caching
- Configurable model selection for different tasks

### 4. Embedding System

Supports multiple embedding providers:
- OpenAI embeddings
- Jina AI embeddings
- Configurable embedding dimensions and models

## Data Models

### Core Data Types

1. **Blob**: Raw input data from users
   - Contains message content, metadata, and timestamps
   
2. **Profile**: Structured user information
   - Topic-based organization
   - Subtopic categorization
   - Update tracking

3. **FactResponse**: Extracted structured facts
   - Topic, subtopic, and memo content
   - Used in extraction pipeline

4. **MergeAddResult**: Profile update operations
   - Add, update, delete operations
   - Delta tracking for changes

### Type System

The project uses TypedDict for structured data and Pydantic for validation:
- Type-safe configuration loading
- Runtime type checking with typeguard
- Promise-based async error handling

## Key Features

### 1. Language Support
- English and Chinese language support
- Localized prompts and processing

### 2. Strict Mode
- Controlled topic/subtopic extraction
- Validation against predefined schemas
- Quality control for profile generation

### 3. Token Management
- Configurable token limits for different operations
- Smart truncation of conversation history
- Efficient prompt engineering

### 4. Async Processing
- Parallel processing of profiles and events
- Promise-based error handling
- Efficient resource utilization

## Extension Points

### 1. Buffer System
Currently empty - can be extended to add:
- Temporary data storage
- Batch processing capabilities
- Background processing queues

### 2. Search System
Currently empty - can be extended to add:
- Vector-based profile search
- Semantic similarity matching
- Advanced query capabilities

### 3. Additional LLM Providers
Easy to extend with new providers by implementing the completion interface

### 4. Custom Embedding Models
Support for additional embedding providers through the existing interface

## Development Guidelines

### 1. Error Handling
- Use Promise-based error handling consistently
- Provide meaningful error messages
- Log errors with context information

### 2. Configuration
- Use environment variables for sensitive data
- Provide sensible defaults
- Validate configuration on startup

### 3. Type Safety
- Use TypedDict for data structures
- Enable runtime type checking
- Maintain type annotations

### 4. Logging
- Use structured logging with context
- Include project and user IDs where applicable
- Configure appropriate log levels

## Performance Considerations

### 1. Token Optimization
- Implement token counting and truncation
- Use efficient prompt templates
- Cache frequently used data

### 2. Async Operations
- Process independent operations in parallel
- Use appropriate async patterns
- Handle concurrent operations safely

### 3. Memory Management
- Clean up unused profiles
- Implement appropriate caching strategies
- Monitor resource usage

## Security Considerations

### 1. API Key Management
- Store API keys in environment variables
- Never commit secrets to code
- Use secure configuration loading

### 2. Input Validation
- Validate all user inputs
- Sanitize data before processing
- Implement rate limiting where appropriate

### 3. Data Privacy
- Handle user data securely
- Implement data retention policies
- Ensure secure data transmission