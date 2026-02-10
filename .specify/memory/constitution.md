<!--
Sync Impact Report:
Version: 0.1.0 -> 1.0.0 (initial ratification)
Modified Principles: N/A (first version)
Added Sections: All sections are new
Removed Sections: N/A
Templates Requiring Updates:
  - .specify/templates/plan-template.md (Constitution Check section filled with lindorm-memobase specific gates)
  - .specify/templates/spec-template.md (aligned with Async-First, Lindorm-Native, Bilingual principles)
  - .specify/templates/tasks-template.md (task categories reflect Storage, Multilingual, Multi-tenant concerns)
Follow-up TODOs: None
-->

# LindormMemobase Constitution

## Core Principles

### I. Library-First Design

LindormMemobase is a Python library package, NOT a hosted service. All architectural decisions MUST prioritize:

- **PyPI Distribution**: Every feature MUST work as an installable package via `pip install lindormmemobase`
- **Self-Contained Operations**: The library MUST manage its own storage connections, LLM calls, and embedding generation without requiring external infrastructure code
- **Multiple Entry Points**: Support `LindormMemobase()`, `from_yaml_file()`, `from_config()` initialization patterns
- **Zero Infrastructure Dependencies**: Users only need Lindorm database credentials and API keys; no sidecar processes, no separate deployment

**Rationale**: As a library, we provide memory capabilities as a drop-in component for LLM applications. Service architecture would create deployment friction and vendor lock-in.

### II. Async-First (NON-NEGOTIABLE)

All I/O operations MUST be asynchronous:

- **Storage Operations**: Every database call (Lindorm Table, Search, Vector) MUST use `async def`
- **LLM Calls**: All OpenAI/LLM completions MUST be non-blocking
- **Initialization**: Storage manager initialization MUST support async contexts
- **Test Framework**: `pytest-asyncio` with `asyncio_mode = "auto"` is mandatory

**Rationale**: Memory extraction involves multiple network round-trips (LLM + embeddings + database). Synchronous operations would block the event loop and kill throughput.

### III. Lindorm-Native Architecture

Storage layer MUST exploit Lindorm's unique capabilities:

- **Five-Engine Integration**: Wide Table, Search, Vector, LTS, AI - each MUST be used for its optimal purpose
- **SQL-First for Checks**: Use `SHOW TABLES LIKE 'name'` instead of `CREATE TABLE IF NOT EXISTS` (20x faster on subsequent runs)
- **Hash Partitioning**: All tables MUST partition by `user_id` for query performance
- **Search Index with Vector**: Embeddings MUST be stored in Lindorm Search index with knn_vector mapping
- **Connection Pooling**: Separate pools per storage type, sized appropriately (default 10 per pool)

**Rationale**: Generic database abstractions would waste Lindorm's unique advantages. The five-engine design is our competitive moat.

### IV. Bilingual Prompt System (Chinese/English)

All LLM prompts MUST support both languages:

- **Dual Prompt Files**: `extract_profile.py` + `zh_extract_profile.py`, same pattern for all prompts
- **Language Configuration**: `ProfileConfig.language` MUST drive prompt selection ("zh" or "en")
- **Localized Extraction**: Chinese conversations use Chinese prompts; English conversations use English prompts
- **No Mixed Languages**: Prompts MUST NOT mix languages within a single template

**Rationale**: LindormMemobase targets Chinese users, but English is essential for global compatibility. Separate prompt files ensure natural phrasing in each language.

### V. Multi-Tenant Isolation

All data operations MUST support project-level isolation:

- **project_id Parameter**: Every storage method MUST accept optional `project_id` filter
- **Project-Specific Config**: `ProfileConfig` can be stored per-project in `ProjectProfileConfigs` table
- **Config Resolution Priority**: (1) explicit parameter → (2) database project config → (3) global config.yaml
- **Cross-Project Queries**: Default behavior queries across all projects; `project_id=None` means "all projects"

**Rationale**: Multi-tenancy enables SaaS applications to use a single LindormMemobase instance for multiple customers while maintaining data isolation.

### VI. Buffer Management for Batch Efficiency

Conversation data MUST flow through buffer system:

- **Token-Based Thresholds**: Buffer flush triggers based on accumulated token size, not blob count
- **Status Tracking**: Each blob has status (idle, processing, completed, failed) to prevent duplicate processing
- **User + Type Scoping**: Buffers are keyed by `(user_id, blob_type, project_id)` tuple
- **Selective Flush**: Support flushing specific blob IDs or all unprocessed blobs

**Rationale**: LLM costs scale with token count, not message count. Batching small conversations into a single LLM call dramatically reduces cost and latency.

## Additional Constraints

### Security Requirements

- **NO Hardcoded Credentials**: API keys MUST come from environment variables or Config object
- **Input Validation**: All user-provided strings MUST be sanitized before database insertion
- **SQL Injection Prevention**: Use parameterized queries for ALL Lindorm SQL operations
- **Secret Protection**: `.env` files MUST be in `.gitignore`; never commit example.env with real keys

### Performance Standards

- **Table Existence Checks**: MUST use `SHOW TABLES LIKE 'name'` for fast re-initialization
- **Index Existence Checks**: MUST use `SHOW INDEX FROM table_name` before index creation
- **Connection Pool Reuse**: Storage objects MUST cache connections; do not create new connection per operation
- **Lazy Initialization**: Heavy resources (TopicConfigStorage) initialize on first access, not in `__init__`

### API Stability

- **Backward Compatibility**: Public API methods MUST NOT break without MAJOR version bump
- **Optional Parameters**: New parameters on existing methods MUST have default values
- **Deprecation Warnings**: Removed features MUST warn for one MINOR version before removal
- **Type Hints**: All public methods MUST have complete type annotations

## Development Workflow

### Testing Strategy

- **Unit Tests**: Fast, isolated tests for utils, prompts, models
- **Integration Tests**: Tests requiring Lindorm connection marked with `@pytest.mark.requires_database`
- **API Key Tests**: Tests using real OpenAI keys marked with `@pytest.mark.requires_api_key`
- **Async Tests**: All async tests use `pytest-asyncio` with auto mode

### Code Review Requirements

- **Security Review**: Any changes touching credentials, SQL, or input validation require review
- **Performance Review**: Storage layer changes must verify connection pooling and fast existence checks
- **Bilingual Review**: Prompt changes must update BOTH English and Chinese versions
- **Breaking Change Review**: API changes require explicit reviewer approval

### Quality Gates

- **Ruff Linting**: MUST pass before commit
- **Type Checking**: Complex modules should use type hints
- **Async Correctness**: No mixing of sync/async I/O in same flow
- **Documentation**: Public API changes update README.md examples

## Governance

### Amendment Process

1. Propose amendment with rationale and impact analysis
2. Update this constitution with incremented version
3. Review implications for plan/spec/tasks templates
4. Update dependent templates if needed
5. Document changes in Sync Impact Report

### Versioning Policy

- **MAJOR**: Breaking changes to core principles (e.g., dropping Async-First)
- **MINOR**: Adding new principles or sections (e.g., adding Multi-Tenant principle)
- **PATCH**: Clarifications, wording improvements, non-semantic changes

### Compliance Review

- All PRs MUST verify compliance with applicable principles
- Violations MUST be documented in `plan.md` Complexity Tracking table
- "Complexity must be justified" rule applies to ALL exceptions

**Version**: 1.0.0 | **Ratified**: 2026-02-09 | **Last Amended**: 2026-02-09
