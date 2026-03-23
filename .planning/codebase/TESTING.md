# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Framework

**Runner:** pytest 8.x
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- `testpaths = ["tests"]`
- `asyncio_mode = "auto"` — async tests run automatically without `@pytest.mark.asyncio`

**Async support:** `pytest-asyncio >= 0.24.0`

**Coverage:** `pytest-cov >= 6.0.0` (available but no minimum threshold enforced)

**Run Commands:**
```bash
# Run all tests
pytest

# Run with short traceback
pytest --tb=short

# Run with coverage
pytest --cov=src/axon --cov-report=term-missing

# Run specific test file
pytest tests/core/test_pipeline.py

# Run specific test class
pytest tests/core/test_pipeline.py::TestRunPipelineBasic

# Run with specific marker
pytest -m allow_update_notice
```

## Test File Organization

**Location:** Tests are in a top-level `tests/` directory, mirroring the `src/axon/` package structure. Tests are NOT co-located with source files.

**Structure:**
```
tests/
├── __init__.py
├── conftest.py                     # Shared fixtures (KuzuBackend fixture)
├── cli/
│   ├── __init__.py
│   └── test_main.py                # CLI command tests
├── core/
│   ├── __init__.py
│   ├── test_calls.py
│   ├── test_community.py
│   ├── test_config.py
│   ├── test_coupling.py
│   ├── test_dead_code.py
│   ├── test_diff.py
│   ├── test_embedder.py
│   ├── test_embedding_text.py
│   ├── test_graph.py
│   ├── test_graph_model.py
│   ├── test_heritage.py
│   ├── test_hybrid_search.py
│   ├── test_imports.py
│   ├── test_kuzu_backend.py
│   ├── test_kuzu_search.py
│   ├── test_parser_phase.py
│   ├── test_parser_python.py
│   ├── test_parser_typescript.py
│   ├── test_pipeline.py
│   ├── test_processes.py
│   ├── test_storage_base.py
│   ├── test_structure.py
│   ├── test_types.py
│   ├── test_walker.py
│   └── test_watcher.py
├── e2e/
│   ├── __init__.py
│   └── test_full_pipeline.py       # Full pipeline integration tests
├── mcp/
│   ├── __init__.py
│   └── test_tools.py               # MCP tool handler tests
└── web/
    ├── __init__.py
    └── test_routes.py              # FastAPI route tests
```

**Naming:**
- Test files: `test_<module_name>.py`
- Test classes: `Test<Scenario>` (e.g., `TestRunPipelineBasic`, `TestParseClassWithMethods`)
- Test methods: `test_<what_is_being_verified>` in snake_case

## Test Structure

**Suite organization:** Tests are grouped into classes by the feature or scenario being tested. Each class typically covers one function or one input variant. This pattern is consistent across all test files.

```python
class TestRunPipelineBasic:
    def test_run_pipeline_basic(self, tmp_repo: Path, storage: KuzuBackend) -> None:
        _, result = run_pipeline(tmp_repo, storage)
        assert isinstance(result, PipelineResult)
        assert result.duration_seconds > 0.0

class TestRunPipelineFileCount:
    def test_run_pipeline_file_count(self, tmp_repo: Path, storage: KuzuBackend) -> None:
        _, result = run_pipeline(tmp_repo, storage)
        assert result.files == 3
```

**One assertion focus per test method:** Most tests verify a single property or behavior. When multiple assertions appear together, they check different aspects of the same output (e.g., checking all fields of one returned object).

**Return type annotations:** All test methods declare `-> None`.

**Setup/teardown:** Handled exclusively via pytest fixtures using `yield` — no `setUp`/`tearDown` methods.

## Fixtures

**Shared fixture in `tests/conftest.py`:**
```python
@pytest.fixture()
def kuzu_backend(tmp_path: Path) -> KuzuBackend:
    """Provide an initialised KuzuBackend in a temporary directory."""
    db_path = tmp_path / "test_db"
    b = KuzuBackend()
    b.initialize(db_path)
    yield b
    b.close()
```

**Local fixtures defined per test file** when the fixture is only relevant to that module. Example from `tests/core/test_pipeline.py`:

```python
@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a small Python repository under a temporary directory."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        "from .auth import validate\n\ndef main():\n    validate()\n",
        encoding="utf-8",
    )
    # ... more files
    return tmp_path

@pytest.fixture()
def storage(tmp_path: Path) -> KuzuBackend:
    backend = KuzuBackend()
    backend.initialize(tmp_path / "test_db")
    yield backend
    backend.close()
```

**Fixture docstrings:** Fixtures include a docstring with a file layout diagram (`Layout::` block) when they create a filesystem structure. This is a codebase-wide convention.

**`tmp_path` usage:** All filesystem-dependent tests use pytest's built-in `tmp_path` fixture. Temporary repositories are built programmatically by writing files with `.write_text(..., encoding="utf-8")`.

**`monkeypatch.chdir`:** CLI tests that depend on `Path.cwd()` use `monkeypatch.chdir(tmp_path)` to control the working directory.

## Mocking

**Framework:** `unittest.mock` — `patch`, `MagicMock`, `patch.object`

**Storage mocking for web/MCP tests:** Tests that don't need a real database use `MagicMock()` with explicit return values configured:

```python
@pytest.fixture
def mock_storage() -> MagicMock:
    storage = MagicMock()
    graph = KnowledgeGraph()
    storage.load_graph.return_value = graph
    storage.get_node.return_value = None
    storage.get_callers_with_confidence.return_value = []
    storage.fts_search.return_value = []
    storage.execute_raw.return_value = []
    return storage
```

**`patch` as context manager** for isolating specific calls:
```python
with patch("axon.cli.main._load_storage", return_value=mock_storage):
    with patch("axon.mcp.tools.handle_query", return_value="1. MyClass"):
        result = runner.invoke(app, ["query", "find classes"])
```

**`side_effect` for failure simulation:**
```python
with patch(
    "axon.core.ingestion.pipeline.embed_graph",
    side_effect=RuntimeError("model not found"),
):
    _, result = run_pipeline(rich_repo, rich_storage)
```

**`patch.object` for patching asyncio:**
```python
with patch.object(real_asyncio, "run") as mock_run:
    result = runner.invoke(app, ["mcp"])
mock_run.assert_called_once()
```

**What NOT to mock:** The ingestion pipeline, parser, graph, and storage backend are tested with real implementations against `tmp_path`-based repositories. Mocking is reserved for external I/O (network, asyncio.run) and the storage layer in web/MCP tests.

## Test Types

**Unit tests (`tests/core/`):**
- Test individual modules in isolation using real implementations (not mocks)
- Ingestion phases (`test_calls.py`, `test_imports.py`, etc.) build a `KnowledgeGraph` directly and call `process_*` functions
- Parser tests (`test_parser_python.py`, `test_parser_typescript.py`) call the parser with inline code strings
- Graph model tests (`test_graph_model.py`) verify node/edge construction and ID generation

**Integration tests (`tests/core/test_pipeline.py`):**
- Run the full pipeline against a programmatically-constructed repository in `tmp_path`
- Verify `PipelineResult` counts (files, symbols, relationships, dead code)
- Test progress callback invocation across all pipeline phases
- Test embedding failure resilience via `patch`

**End-to-end tests (`tests/e2e/test_full_pipeline.py`):**
- Run the full pipeline on a multi-language repo (Python + TypeScript)
- Verify FTS search, MCP tool outputs (`handle_context`, `handle_impact`, `handle_query`, `handle_dead_code`)
- Verify idempotency: running the pipeline twice produces the same counts and no duplicate nodes in the DB
- Verify specific relationship types (contains, defines, imports, calls) via `storage.execute_raw`

**CLI tests (`tests/cli/test_main.py`):**
- Use `typer.testing.CliRunner` to invoke commands
- Test all CLI commands: `analyze`, `status`, `list`, `clean`, `query`, `context`, `impact`, `dead-code`, `cypher`, `setup`, `watch`, `diff`, `mcp`, `host`, `serve`, `ui`
- Test error paths (no index, invalid input) and success paths
- Test the global registry (`_register_in_global_registry`) with collision and cleanup scenarios
- Use `autouse` fixture to suppress update notices; a `@pytest.mark.allow_update_notice` marker re-enables them for update-notifier-specific tests

**Web route tests (`tests/web/test_routes.py`):**
- Use `fastapi.testclient.TestClient` against a manually-assembled FastAPI app
- Two fixtures: `client` (no repo path) and `client_with_repo` (with real `tmp_path`)
- Cover all API endpoints: `/graph`, `/overview`, `/host`, `/node/{id}`, `/search`, `/dead-code`, `/coupling`, `/health`, `/communities`, `/processes`, `/cypher`, `/tree`, `/file`, `/diff`, `/reindex`, `/impact`, `/events`
- Cypher guard tests extensively cover blocked write keywords (CREATE, DELETE, SET, DROP, MERGE, DETACH DELETE, REMOVE, INSTALL, LOAD, COPY)

**MCP tool tests (`tests/mcp/test_tools.py`):**
- Test all `handle_*` functions from `src/axon/mcp/tools.py` and resource handlers from `src/axon/mcp/resources.py`
- Use a shared `mock_storage` fixture with typed `SearchResult` and `GraphNode` return values

## Custom Markers

```ini
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "allow_update_notice: run CLI tests with the real update notifier enabled",
]
```

The `allow_update_notice` marker is used to test the update notification behavior in `tests/cli/test_main.py`. All other CLI tests suppress the notifier via an `autouse` fixture.

## Common Patterns

**Async testing:**
`asyncio_mode = "auto"` means async test functions work without decoration. Define an `async def test_*` method directly.

**In-memory code snippets for parser tests:**
Parser tests define code as inline string constants (class-level `CODE` attributes) and verify parsed output fields:
```python
class TestParseSimpleFunction:
    CODE = (
        'def greet(name: str) -> str:\n'
        '    return f"Hello, {name}"\n'
    )

    def test_symbol_count(self, parser: PythonParser) -> None:
        result = parser.parse(self.CODE, "test.py")
        assert len(result.symbols) == 1
```

**Error path testing:**
```python
def test_status_no_index(self, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "No index found" in result.output
```

**DB-level verification in e2e tests:**
```python
rows = storage.execute_raw(
    "MATCH ()-[r:CodeRelation]->() "
    "WHERE r.rel_type = 'calls' "
    "RETURN count(r)"
)
assert rows[0][0] > 0
```

**Factory helpers in web tests:**
`_sample_node(...)` and `_sample_edge(...)` helper functions in `tests/web/test_routes.py` provide convenient construction of `GraphNode` and `GraphRelationship` with sane defaults and keyword overrides.

## Test Coverage Gaps

**Watcher / incremental re-index:** `tests/core/test_watcher.py` exists, but `reindex_files` in `src/axon/core/ingestion/pipeline.py` has limited coverage — the global phases (communities, dead code, coupling) are not re-run during incremental reindex and this behavior is not explicitly tested.

**Embedding generation:** The embedder is tested in `tests/core/test_embedder.py`, but integration of vector search results into MCP tool output is not covered by current e2e tests.

**Web SSE events endpoint:** `tests/web/test_routes.py::TestEventsEndpoint` only asserts a 200 status code; streaming behavior and event dispatch are not tested.

**MCP server transport layer:** `src/axon/mcp/server.py` is tested indirectly through CLI tests that mock `asyncio.run`. The stdio and HTTP MCP transports themselves are not tested.

**`axon diff` with real git:** `tests/core/test_diff.py` and the CLI `diff` command tests do not exercise against an actual git repository. The `resolve_coupling` phase in `test_pipeline.py` asserts `coupled_pairs == 0` (no git repo), so coupling logic is effectively untested end-to-end.

**Web frontend build artifacts:** The frontend (`src/axon/web/frontend/dist/`) is excluded from test scope. No frontend tests exist in this repository.

**Neo4j optional backend:** The `neo4j` optional dependency exists in `pyproject.toml` but no backend implementation or tests for it are present in the current codebase.

---

*Testing analysis: 2026-03-23*
