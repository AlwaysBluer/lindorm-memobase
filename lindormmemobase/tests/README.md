# Lindorm Storage Integration Tests

This directory contains comprehensive integration tests for both LindormSearch (OpenSearch-compatible) and LindormTable (MySQL-compatible) storage implementations.

## Prerequisites

1. **Environment Configuration**: Ensure your `.env` file is properly configured with:
   - `MEMOBASE_OPENSEARCH_HOST`, `MEMOBASE_OPENSEARCH_PORT`, `MEMOBASE_OPENSEARCH_USERNAME`, `MEMOBASE_OPENSEARCH_PASSWORD`
   - `MEMOBASE_MYSQL_HOST`, `MEMOBASE_MYSQL_PORT`, `MEMOBASE_MYSQL_USERNAME`, `MEMOBASE_MYSQL_PASSWORD`, `MEMOBASE_MYSQL_DATABASE`
   - `MEMOBASE_EMBEDDING_DIM` (for vector dimension testing)

2. **Dependencies**: Install test dependencies:
   ```bash
   pip install -r tests/requirements.txt
   ```

## Running Tests

### Option 1: Run All Tests (Recommended)
```bash
# Run comprehensive test suite
python tests/test_lindorm_storage.py

# Run with verbose output
python tests/test_lindorm_storage.py --verbose
```

### Option 2: Run Specific Storage Tests
```bash
# Run only LindormSearch tests
python tests/test_lindorm_storage.py --search

# Run only LindormTable tests  
python tests/test_lindorm_storage.py --table
```

### Option 3: Run Individual Test Files
```bash
# Run search tests using pytest
pytest tests/test_lindorm_search.py -v -s

# Run table tests using pytest
pytest tests/test_lindorm_table.py -v -s
```

## Test Coverage

### LindormSearch Tests (`test_lindorm_search.py`)
- ✅ **Connection Test**: Verify connectivity to Lindorm Search
- ✅ **Indices Creation**: Test automatic index creation with proper mappings
- ✅ **Store Event with Embedding**: Test storing events with vector embeddings
- ✅ **Store Event Gist**: Test storing event summaries/gists
- ✅ **Hybrid Search Events**: Test vector + text search for events
- ✅ **Hybrid Search Gists**: Test vector + text search for event gists
- ✅ **Error Handling**: Test graceful error handling
- ✅ **Store without Embedding**: Test handling of null embeddings

### LindormTable Tests (`test_lindorm_table.py`)
- ✅ **Connection Test**: Verify connectivity to Lindorm Wide Table
- ✅ **Table Creation**: Test automatic table creation with proper schema
- ✅ **Add Profiles**: Test inserting user profiles
- ✅ **Get User Profiles**: Test querying user profiles with filtering
- ✅ **Update Profiles**: Test updating existing profiles
- ✅ **Delete Profiles**: Test removing profiles
- ✅ **Concurrent Operations**: Test thread-safe concurrent database operations
- ✅ **Large Content Handling**: Test handling of large text content (10KB+)
- ✅ **JSON Attributes**: Test complex nested JSON attribute storage/retrieval
- ✅ **Error Handling**: Test handling of invalid operations

## Test Data Management

- **Automatic Cleanup**: All tests include automatic cleanup of test data
- **Isolation**: Each test uses unique user IDs to avoid conflicts
- **Non-Destructive**: Tests only create/modify/delete their own test data

## Expected Output

### Successful Run
```
🚀 Lindorm Storage Integration Test Suite
============================================================

Configuration & Connectivity Tests
============================================================
✅ Configuration loaded successfully
📋 Configuration Summary:
   - Language: zh
   - LLM Model: qwen-max-latest
   - Embedding Model: text-embedding-v4
   - Embedding Dimension: 1024
   - OpenSearch Host: your-host:30070
   - MySQL Host: your-host:33060

LindormSearch Storage Tests
============================================================
✅ Connection Test
✅ Indices Creation
✅ Store Event with Embedding
✅ Store Event Gist
✅ Hybrid Search Events
✅ Hybrid Search Gists
✅ Error Handling
✅ Store without Embedding

📊 LindormSearch Results: 8 passed, 0 failed

LindormTable Storage Tests
============================================================
✅ Connection Test
✅ Table Creation
✅ Add Profiles
✅ Get User Profiles
✅ Update Profiles
✅ Delete Profiles
✅ Concurrent Operations
✅ Large Content Handling
✅ JSON Attributes
✅ Error Handling

📊 LindormTable Results: 10 passed, 0 failed

📋 Final Test Summary
Total Results:
  ✅ Passed: 18
  ❌ Failed: 0

✅ All tests passed! 🎉
```

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify your `.env` configuration
   - Ensure Lindorm services are running and accessible
   - Check network connectivity and firewall settings

2. **Permission Errors**
   - Verify database user has necessary permissions (CREATE, INSERT, UPDATE, DELETE)
   - For OpenSearch, ensure user can create indices and perform searches

3. **Schema Issues**
   - Tests automatically create required tables/indices
   - If schema conflicts occur, manually drop test tables/indices and re-run

### Debug Mode
Run with Python's verbose logging:
```bash
PYTHONPATH=. python -v tests/test_lindorm_storage.py --verbose
```

## Performance Notes

- **Search Tests**: Include 2-second delays for index synchronization
- **Concurrent Tests**: Test connection pooling under load
- **Large Content**: Tests with 10KB+ content to verify text handling
- **Vector Operations**: Tests with full embedding dimension vectors

## Security

- Tests use read-only operations where possible
- All test data is clearly marked and automatically cleaned up
- No production data is accessed or modified
- Sensitive configuration (passwords, hosts) is loaded from environment variables only