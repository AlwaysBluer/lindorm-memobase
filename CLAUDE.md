# CLAUDE.md

This file contains important notes for Claude Code (claude.ai/code) when working with this repository.

Use .venv/ the virutal enviroment when running python scripts.

## Lindorm Wide Table SQL Best Practices

### Checking Table Existence

Use `SHOW TABLES LIKE 'table_name'` instead of `CREATE TABLE IF NOT EXISTS` for faster checks:

```sql
-- Fast: ~0.05 sec
SHOW TABLES LIKE 'UserProfiles';

-- Slow: ~20 sec (even if table exists)
CREATE TABLE IF NOT EXISTS UserProfiles (...);
```

**Example implementation**:
```python
cursor.execute("SHOW TABLES LIKE 'UserProfiles'")
if cursor.fetchone():
    # Table exists, skip creation
    return
```

### Checking Index Existence

Use `SHOW INDEX FROM table_name` to check for existing indexes:

```sql
-- Returns multiple rows, one per index
SHOW INDEX FROM UserProfiles;

-- Column order (0-based):
-- row[0] = TABLE_SCHEMA
-- row[1] = DATA_TABLE
-- row[2] = INDEX_NAME  ← Check this
-- row[3] = INDEX_STATE
-- ...
```

**Example implementation**:
```python
cursor.execute("SHOW INDEX FROM UserProfiles")
index_exists = False
for row in cursor.fetchall():
    if len(row) >= 3 and row[2] == 'srh_idx':  # INDEX_NAME is at index 2
        index_exists = True
        break

if index_exists:
    # Index exists, skip creation
    return
```

### Performance Comparison

| Operation | First Time | Subsequent Times |
|-----------|------------|-------------------|
| `CREATE TABLE IF NOT EXISTS` | ~20s | ~20s |
| `SHOW TABLES LIKE '...'` | ~20s | **~0.05s** |
| `CREATE INDEX IF NOT EXISTS` | ~20s | ~20s |
| `SHOW INDEX FROM ...` | ~20s | **~0.06s** |

**Key insight**: Use `SHOW` commands for existence checks to avoid slow operations on repeated initializations.

### Connection Pool Configuration

Lindorm wide table has separate connection pools per storage type:

```python
lindorm_table_pool_size: 10  # Per-storage pool size
lindorm_executor_workers: 20  # Thread pool for async operations (can be > pool_size)

# Actual total connections = 4 storages × 10 = 40 connections
# - LindormTableStorage.pool (10)
# - LindormEventsStorage.pool (10)
# - LindormEventGistsStorage.pool (10)
# - LindormBufferStorage.pool (10)
```

**Important**: Pool creation happens on first use (lazy initialization), not during `__init__`.

### Search Index Creation

Search indexes on Lindorm wide table support both structured and vector search:

```sql
CREATE INDEX srh_idx USING SEARCH ON UserProfiles(
    user_id,
    project_id,
    profile_id,
    topic,
    subtopic,
    content(type=text,analyzer=ik,indexed=true),
    created_at,
    updated_at,
    embedding(mapping={
        "type": "knn_vector",
        "dimension": 1024,
        "data_type": "float",
        "method": {
            "engine": "lvector",
            "name": "hnsw",
            "space_type": "l2",
            "parameters": {
                "m": 24,
                "ef_construction": 500
            }
        }
    })
) PARTITION BY hash(user_id) WITH (
    SOURCE_SETTINGS='{"excludes": ["embedding"]}',
    INDEX_SETTINGS='{"index": {"knn": true}}'
);
```

### Official Documentation Links

- [SHOW TABLES](https://help.aliyun.com/zh/lindorm/developer-reference/show-tables)
- [SHOW INDEX](https://help.aliyun.com/zh/lindorm/developer-reference/the-show-index)

## Active Technologies
- Python 3.11+ (async/await required) + Pydantic (config/models), asyncio (async operations), mysql-connector-python (Lindorm wide table), pytest-asyncio (testing) (001-profile-merge-strategy)
- Lindorm Wide Table engine (PendingProfiles table, existing UserProfiles table), partitioned by user_id (001-profile-merge-strategy)

## Recent Changes
- 001-profile-merge-strategy: Added Python 3.11+ (async/await required) + Pydantic (config/models), asyncio (async operations), mysql-connector-python (Lindorm wide table), pytest-asyncio (testing)
