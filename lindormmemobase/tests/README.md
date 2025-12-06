# Lindorm Memobase Test Suite

This directory contains comprehensive unit and integration tests for the lindorm-memobase library.

## Directory Structure

```
tests/
├── __init__.py                  # Test package initialization
├── conftest.py                  # Shared pytest fixtures and configuration
├── README.md                    # This file
│
├── unit/                        # Unit tests (fast, isolated)
│   ├── test_config.py           # Configuration loading and validation
│   ├── test_models_blob.py      # Blob models validation
│   ├── test_models_promise.py   # Promise pattern tests
│   └── ...                      # More unit tests
│
├── integration/                 # Integration tests (slower, requires services)
│   └── ...                      # Integration test files
│
├── fixtures/                    # Test data and fixtures
│   ├── sample_blobs.py          # Sample ChatBlob, DocBlob instances
│   ├── sample_profiles.py       # Sample user profile data
│   ├── sample_conversations.py  # Sample chat messages
│   └── mock_responses.py        # Mock LLM/embedding responses
│
└── mocks/                       # Mock implementations
    ├── mock_llm.py              # Mock LLM client
    ├── mock_embedding.py        # Mock embedding client
    └── mock_storage.py          # Mock storage backends
```

## Running Tests

### Prerequisites

```bash
# Install development dependencies
pip install -e ".[dev]"

# Or install test dependencies directly
pip install pytest pytest-asyncio
```

### Run All Tests

```bash
pytest
```

### Run Unit Tests Only

```bash
pytest -m unit
```

### Run Integration Tests

```bash
pytest -m integration
```

### Run with Coverage

```bash
pytest --cov=lindormmemobase --cov-report=html
```

### Run Specific Test File

```bash
pytest lindormmemobase/tests/unit/test_models_blob.py -v
```

### Run Specific Test Class

```bash
pytest lindormmemobase/tests/unit/test_models_blob.py::TestChatBlob -v
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Tests requiring external services
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.requires_api_key` - Tests needing real API credentials
- `@pytest.mark.requires_database` - Tests needing Lindorm connection
- `@pytest.mark.asyncio` - Async test handling

## Test Coverage Summary

### Completed (Phase 1-2)

#### Unit Tests
- ✅ **Blob Models** (`test_models_blob.py`) - 34 tests
  - OpenAICompatibleMessage validation
  - ChatBlob, DocBlob, CodeBlob creation
  - BlobType enum handling
  - Blob serialization and conversion

- ✅ **Promise Pattern** (`test_models_promise.py`) - 22 tests
  - Promise resolve/reject functionality
  - Error handling and data extraction
  - Response model conversion

- ✅ **Configuration** (`test_config.py`) - 26 tests
  - YAML configuration loading
  - Environment variable processing
  - Configuration validation

#### Test Infrastructure
- ✅ **Fixtures** - Sample data for testing
  - `sample_blobs.py` - Realistic blob instances
  - `sample_profiles.py` - User profile data
  - `sample_conversations.py` - Chat message sequences
  - `mock_responses.py` - Mock API responses

- ✅ **Mocks** - Mock implementations
  - `mock_llm.py` - Mock LLM client with deterministic responses
  - `mock_embedding.py` - Mock embedding client with deterministic vectors
  - `mock_storage.py` - In-memory storage backends

### Current Test Statistics

- **Total Tests**: 82
- **Passing**: 56
- **Execution Time**: < 1 second for unit tests

### In Progress

- Utility function tests
- Main API tests
- Integration tests

## Writing New Tests

### Unit Test Example

```python
import pytest
from lindormmemobase.models.blob import ChatBlob, BlobType

@pytest.mark.unit
class TestMyFeature:
    def test_basic_functionality(self):
        """Test description."""
        blob = ChatBlob(messages=[])
        assert blob.type == BlobType.chat
```

### Using Fixtures

```python
@pytest.mark.unit
def test_with_fixture(mock_config):
    """Test using mock configuration fixture."""
    assert mock_config.language == "en"
    assert mock_config.test_skip_persist is True
```

### Testing Async Functions

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_function():
    """Test async functionality."""
    result = await some_async_function()
    assert result is not None
```

## Mock Usage Examples

### Mock LLM Client

```python
from lindormmemobase.tests.mocks.mock_llm import MockLLMClient

client = MockLLMClient(default_response="Test response")
response = await client.create_completion(messages=[...])
assert "Test response" in response["choices"][0]["message"]["content"]
```

### Mock Embedding Client

```python
from lindormmemobase.tests.mocks.mock_embedding import MockEmbeddingClient

client = MockEmbeddingClient(dimension=1536)
embedding = await client.create_embedding("test text")
assert len(embedding) == 1536
```

### Mock Storage

```python
from lindormmemobase.tests.mocks.mock_storage import MockTableStorage

storage = MockTableStorage()
storage.initialize_tables()
result = await storage.add_profiles(user_id="test", profiles=["profile1"], ...)
assert result.ok()
```

## Best Practices

### Unit Tests

1. **Isolation**: Each test should be independent
2. **Speed**: Keep tests fast (milliseconds)
3. **Clarity**: Use descriptive test names
4. **Mocking**: Mock all external dependencies
5. **Single Assertion**: Focus each test on one behavior

### Integration Tests

1. **Setup/Teardown**: Clean up test data
2. **Idempotency**: Tests should produce same results on repeated runs
3. **Real Scenarios**: Test real-world usage patterns
4. **Error Cases**: Include failure scenario tests

### Test Organization

1. **Group Related Tests**: Use test classes
2. **Clear Names**: Test names should describe what is tested
3. **Documentation**: Add docstrings to test classes and methods
4. **Fixtures**: Use fixtures for reusable test data

## Troubleshooting

### Import Errors

If you encounter import errors related to tiktoken or network connectivity:
- Tests import heavy dependencies inside fixtures to avoid initialization issues
- Ensure you're running tests from the project root directory

### Fixture Not Found

```python
# Fixtures are defined in conftest.py
# They are automatically available to all tests
def test_example(minimal_config):  # minimal_config is auto-injected
    assert minimal_config is not None
```

### Async Test Issues

```python
# Use @pytest.mark.asyncio for async tests
@pytest.mark.asyncio
async def test_async_code():
    result = await async_function()
    assert result
```

## Contributing

When adding new features:
1. Write tests before implementing (TDD)
2. Ensure coverage doesn't decrease
3. Follow existing test patterns
4. Update this README if adding new test categories

## Coverage Goals

- Core API (main.py): 90%
- Storage layer: 85%
- Models: 95%
- Utilities: 90%
- Overall: 80%

## CI/CD Integration

Tests are designed to run in CI/CD pipelines:
- Unit tests run on every pull request
- Integration tests run with mock services (fast tier)
- Full integration tests run nightly with real services
