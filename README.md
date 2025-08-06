# LindormMemobase

A lightweight memory extraction and profile management system for LLM applications. This package provides core functionality for extracting structured information from conversations, managing user profiles, and performing embedding-based searches.

## Features

- **Memory Extraction**: Extract structured facts from conversational data
- **Profile Management**: Organize user information by topics and subtopics
- **Embedding Search**: Vector-based similarity search capabilities
- **Flexible Storage**: Support for MySQL and OpenSearch backends
- **Multi-language**: English and Chinese language processing
- **Async Processing**: Efficient asynchronous processing pipeline

## Quick Start

### Installation

```bash
# Development installation
pip install -e .

# Or install from source
git clone <repository-url>
cd lindorm-memobase
pip install -e .
```

### Basic Usage

```python
import asyncio
from lindormmemobase import MemoBaseAPI, Blob, Config
from datetime import datetime

async def main():
    # Load configuration
    config = Config.load_config()
    api = MemoBaseAPI(config)
    
    # Create conversation blobs
    blobs = [
        Blob(
            content="I love playing guitar and learning jazz",
            timestamp=datetime.now(),
            user_id="user123",
            source="chat"
        )
    ]
    
    # Process and extract memory
    result = await api.process_blobs(blobs)
    if result.ok():
        print("Memory extraction successful!")
        print(f"Facts: {result.data().facts}")

asyncio.run(main())
```

## Configuration

### Environment Setup

1. Copy the example environment file:
   ```bash
   cp example.env .env
   ```

2. Edit `.env` with your API keys:
   ```bash
   MEMOBASE_LLM_API_KEY=your-openai-api-key
   MEMOBASE_EMBEDDING_API_KEY=your-embedding-api-key
   ```

3. Copy and customize the config file:
   ```bash
   cp config.yaml.example config.yaml
   ```

### Configuration Files

- **`.env`**: Environment variables for sensitive data (API keys, credentials)
- **`config.yaml`**: Application configuration (models, limits, features)
- **Priority**: Default values < `config.yaml` < Environment variables

## Architecture

### Core Components

- **`core/extraction/`**: Memory extraction pipeline
- **`models/`**: Data models (Blob, Profile, Response types)
- **`storage/`**: Storage backends (MySQL, OpenSearch)
- **`embedding/`**: Embedding providers (OpenAI, Jina)
- **`llm/`**: LLM providers and completion interface

### Processing Pipeline

```
Raw Blobs → Truncation → Entry Summary → [Profile Extraction + Event Processing] → Structured Response
```

## Building and Distribution

### Development Build

```bash
# Install in development mode
pip install -e .

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=lindormmemobase --cov-report=html
```

### Production Build

Using `build` (recommended):
```bash
# Install build tool
pip install build

# Build wheel and source distribution
python -m build

# Output files will be in dist/
ls dist/
# lindormmemobase-0.1.0-py3-none-any.whl
# lindormmemobase-0.1.0.tar.gz
```

Using `setuptools` directly:
```bash
# Build wheel
python setup.py bdist_wheel

# Build source distribution  
python setup.py sdist
```

### Installation from Built Package

```bash
# Install from wheel
pip install dist/lindormmemobase-0.1.0-py3-none-any.whl

# Or install from source distribution
pip install dist/lindormmemobase-0.1.0.tar.gz
```

### Publishing to PyPI

```bash
# Install twine for uploading
pip install twine

# Upload to TestPyPI first
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# Upload to PyPI
twine upload dist/*
```

## Examples and Cookbooks

Check the `cookbooks/` directory for practical examples:

- **`basic_usage.py`**: Core API usage
- **`profile_management.py`**: Working with user profiles
- **`embedding_search.py`**: Vector search examples
- **`async_processing.py`**: Batch processing patterns

## Documentation

- **`docs/`**: Comprehensive documentation
- **`docs/quickstart.md`**: Getting started guide
- **`docs/api_reference.md`**: API documentation
- **`docs/architecture.md`**: System architecture overview

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_lindorm_storage.py -v

# Run with coverage report
pytest tests/ --cov=lindormmemobase --cov-report=html
```

## Requirements

- Python 3.12+
- OpenAI API key (for LLM and embedding services)
- MySQL or OpenSearch (for storage backends)

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Support

For issues and questions:
- Check the documentation in `docs/`
- Review examples in `cookbooks/`
- Open an issue on the repository