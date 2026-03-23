<!-- GSD:project-start source:PROJECT.md -->
## Project

**Axon — Language Extension: C#, UE5 C++, AngelScript**

Axon is a code intelligence engine that ingests source repositories into an embedded graph database (KuzuDB) and exposes the resulting knowledge graph through a CLI, MCP server (15 AI tools), and a React web UI. It currently supports Python, TypeScript, TSX, and JavaScript via tree-sitter parsers. This milestone adds three new language parsers — C#, Unreal Engine 5 C++, and UnrealAngel AngelScript — with full UE5-awareness built in from the start.

**Core Value:** AI agents and developers can navigate, search, and understand Unreal Engine 5 codebases the same way they can Python and TypeScript ones — with correct UE5 macro semantics, module boundaries, and Blueprint exposure surfaced in the graph.

### Constraints

- **Tech stack**: tree-sitter for parsing — consistent with existing Python/TS parsers; new grammars added as pyproject.toml dependencies
- **Parser protocol**: new parsers must implement `LanguageParser` from `base.py` — `ParseResult` dataclass drives all downstream phases unchanged
- **Graph model**: new node/relationship types go in `model.py` enums; KuzuDB schema creation is automatic from the enum
- **Compatibility**: existing Python/TS indexing must be unaffected; dead-code logic changes must not regress existing exemption tests (818 tests currently passing)
- **No new infrastructure**: no additional databases, services, or runtimes introduced
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 — entire backend, CLI, MCP server, ingestion pipeline, graph storage
- TypeScript 5.6 — frontend SPA in `src/axon/web/frontend/src/`
- JavaScript (ES modules) — Vite config, test harness glue
- TSX — React component files under `src/axon/web/frontend/src/components/`
## Runtime
- Python runtime: CPython 3.11 (pinned via `.python-version`)
- Node.js: 20 (used in CI for frontend build; version from `.github/workflows/publish.yml`)
- The shipped wheel embeds a pre-built frontend dist — no Node required at install time
- Python: `uv` (used in CI via `astral-sh/setup-uv`; `hatchling` is the build backend)
- Frontend: `npm` — lockfile at `src/axon/web/frontend/package-lock.json`
- Lockfile: `package-lock.json` present; no Python lockfile committed (uv generates on sync)
## Frameworks
- `typer >= 0.15.0` — CLI framework; entry point `axon.cli.main:app`
- `fastapi >= 0.115.0` — Web API framework; app factory in `src/axon/web/app.py`
- `uvicorn[standard] >= 0.34.0` — ASGI server; launched from CLI `axon serve` command
- `mcp >= 1.0.0` — Model Context Protocol SDK; MCP server in `src/axon/mcp/server.py`
- `sse-starlette >= 2.0.0` — SSE streaming middleware; used in `src/axon/web/routes/events.py`
- React 18.3 — UI framework; SPA entry in `src/axon/web/frontend/src/App.tsx`
- Tailwind CSS 4.0 — utility CSS; configured via `@tailwindcss/vite` plugin
- Vite 6.0 — build tool and dev server; config at `src/axon/web/frontend/vite.config.ts`
- `pytest >= 8.0.0` — test runner
- `pytest-asyncio >= 0.24.0` — async test support; `asyncio_mode = "auto"` in `pyproject.toml`
- `pytest-cov >= 6.0.0` — coverage reporting
- Tests in `tests/` with subdirectories `cli/`, `core/`, `e2e/`, `mcp/`, `web/`
- `hatchling` — Python wheel build backend; configured in `pyproject.toml [build-system]`
- `ruff >= 0.9.0` — linter and formatter; target `py311`, line length 100
## Key Dependencies
- `kuzu >= 0.11.0` — embedded property graph database with Cypher query support
- `tree-sitter >= 0.25.0` — core parser library (Rust-backed)
- `tree-sitter-python >= 0.23.0` — Python grammar; used in `src/axon/core/parsers/python_lang.py`
- `tree-sitter-javascript >= 0.23.0` — JavaScript grammar; used in `src/axon/core/parsers/typescript.py`
- `tree-sitter-typescript >= 0.23.0` — TypeScript/TSX grammar; used in `src/axon/core/parsers/typescript.py`
- `fastembed >= 0.7.0` — local embedding model runner; no external API call required
- `igraph >= 1.0.0` — in-memory graph library for community detection algorithms
- `leidenalg >= 0.11.0` — Leiden community detection algorithm; used in `src/axon/core/ingestion/community.py`
- `watchfiles >= 1.0.0` — Rust-backed file system watcher; used in `src/axon/core/ingestion/watcher.py`
- `rich >= 13.0.0` — terminal output formatting; progress bars, styled console output in CLI
- `pathspec >= 1.0.4` — gitignore pattern matching; used in `src/axon/config/ignore.py`
- `anyio` — async compatibility layer; used in CLI for async execution
- `neo4j >= 5.0.0` — optional alternative graph backend (`pyproject.toml [project.optional-dependencies] neo4j`)
## Frontend Key Dependencies
- `graphology 0.25.4` — directed graph data structure
- `graphology-layout-forceatlas2 0.10.1` — ForceAtlas2 layout algorithm
- `graphology-layout-noverlap 0.4.2` — overlap removal layout
- `sigma 3.0.0` — WebGL graph renderer; custom canvas renderer implemented in `src/axon/web/frontend/src/components/graph/GraphCanvas.tsx`
- `zustand 5.0.0` — lightweight React state management
- `ky 1.7.0` — fetch-based HTTP client; used in `src/axon/web/frontend/src/api/client.ts`
- `cmdk 1.0.0` — command palette component
- `lucide-react 0.460.0` — icon library
- `class-variance-authority 0.7.1` + `tailwind-merge 2.6.0` + `clsx 2.1.1` — class name utilities
- `shiki 1.0.0` — syntax highlighting (code view panel)
- `dompurify 3.3.1` — HTML sanitization
## Configuration
- No required environment variables for core functionality
- Database path defaults to `.axon/kuzu/` in the current working directory
- `.env` file presence noted but contents not read
- `pyproject.toml` — Python project config, dependencies, ruff rules, pytest settings
- `src/axon/web/frontend/package.json` — frontend dependencies
- `src/axon/web/frontend/vite.config.ts` — Vite build configuration (TypeScript)
- Frontend built into `src/axon/web/frontend/dist/` and bundled into the Python wheel
## Platform Requirements
- Python 3.11+
- Node.js 20 (for frontend development only)
- Git (required for coupling analysis — `subprocess.run(["git", "log", ...])` in `src/axon/core/ingestion/coupling.py`)
- No Docker required; everything runs in-process
- Single `pip install axoniq` installs the complete stack
- Distributed as a wheel on PyPI (package name: `axoniq`)
- Default port: 8420 (web server), 8421 (managed/host mode)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Source modules use `snake_case.py` (e.g., `kuzu_backend.py`, `parser_phase.py`, `dead_code.py`)
- Test files are prefixed `test_` and mirror the module name (e.g., `test_kuzu_backend.py`, `test_parser_python.py`)
- `__init__.py` files are present in every package but are usually empty or contain re-exports only
- Public functions use `snake_case` (e.g., `run_pipeline`, `walk_repo`, `process_imports`)
- Private/internal helpers are prefixed with a single underscore: `_load_storage`, `_build_meta`, `_fetch_latest_version`
- Ingestion phase functions follow the pattern `process_<noun>` (e.g., `process_calls`, `process_communities`, `process_dead_code`)
- Parser extraction methods follow `_extract_*` per the CONTRIBUTING.md guidance
- `PascalCase` throughout (e.g., `KuzuBackend`, `PipelineResult`, `AxonRuntime`, `LanguageParser`)
- Dataclasses used extensively for data containers: `GraphNode`, `GraphRelationship`, `FileEntry`, `SymbolInfo`, `ParseResult`
- Abstract base classes use the `ABC` mixin directly (e.g., `LanguageParser(ABC)`)
- `snake_case` for local variables and instance attributes
- Module-level constants are `UPPER_SNAKE_CASE` (e.g., `DEFAULT_HOST`, `DEFAULT_PORT`, `UPDATE_CHECK_URL`, `_NODE_PROPERTIES`)
- Private module-level constants prefixed with underscore: `_SYMBOL_LABELS`, `_LABEL_MAP`, `_NODE_TABLE_NAMES`
- Enum members are `UPPER_SNAKE_CASE` (e.g., `NodeLabel.FILE`, `RelType.COUPLED_WITH`, `NodeLabel.TYPE_ALIAS`)
- Enum values are lowercase strings matching the graph/database representation (e.g., `"file"`, `"type_alias"`)
## Code Style
- `E` — pycodestyle errors
- `F` — pyflakes
- `I` — isort (import ordering)
- `N` — pep8-naming
- `W` — pycodestyle warnings
## Import Organization
## Type Annotation Patterns
- **All public function signatures are fully annotated** — parameters and return types
- `from __future__ import annotations` used universally, enabling forward references without quotes
- `Path` (from `pathlib`) preferred over `str` for filesystem paths in signatures
- Union types use the `X | Y` syntax (Python 3.10+ style), enabled by `from __future__ import annotations`
- `Optional[X]` appears only in the CLI layer (`from typing import Optional`); elsewhere `X | None` is used
- `Protocol` with `@runtime_checkable` used for the `StorageBackend` interface in `src/axon/core/storage/base.py`
- `dataclass` + `field(default_factory=list)` for mutable default fields — never bare mutable defaults
- `dataclass(slots=True)` used for `AxonRuntime` in `src/axon/runtime.py`
- Generics use `list[T]`, `dict[K, V]`, `tuple[...]` (lowercase built-in forms, not `List`/`Dict` from `typing`)
- `frozenset` used for immutable sets of constants (e.g., `_SYMBOL_LABELS`, `_PRUNE_DIRS`)
## Error Handling Patterns
- User-facing errors printed with `console.print("[red]Error:[/red] ...")` then `raise typer.Exit(code=1)`
- Never raises raw exceptions to the user; all error paths are caught and formatted
- `(ValueError, RuntimeError)` caught at the command boundary and re-raised as `typer.Exit`
- Errors that must not crash a phase are caught with broad `except Exception` and logged via `logger.warning(..., exc_info=True)` — see embedding phase in `run_pipeline`
- `(json.JSONDecodeError, OSError)` commonly paired for file I/O failure handling
- `(subprocess.TimeoutExpired, FileNotFoundError)` paired for external process calls
- DB errors propagate as `RuntimeError` to the web/CLI layer, which catches them for HTTP 400/500 or typer exit
## Comments and Documentation
## Module Structure Patterns
## Configuration Approach
## Design Patterns
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- In-memory graph (`KnowledgeGraph`) built during ingestion, then bulk-loaded to KuzuDB
- Storage abstracted behind a `StorageBackend` Protocol — `KuzuBackend` is the only concrete implementation
- Incremental re-indexing driven by `watchfiles` with debounced global phases
- All three surfaces (CLI, MCP, Web) share the same `tools.py` handler functions
- Hybrid search (BM25 FTS + cosine-similarity vector) merged with Reciprocal Rank Fusion
## Layers
- Purpose: User-facing entry point; orchestrates all other subsystems
- Location: `src/axon/cli/main.py`
- Contains: `typer` app, command handlers, host/lifecycle management helpers
- Depends on: `ingestion.pipeline`, `storage.kuzu_backend`, `mcp.server`, `web.app`, `runtime`
- Used by: End-users and `axon serve --watch` (which re-invokes itself as a background subprocess)
- Purpose: Shared state for host processes; carries storage, repo path, watch flag, asyncio lock, and event listener list
- Location: `src/axon/runtime.py` (`AxonRuntime` dataclass)
- Depends on: `storage.base.StorageBackend`
- Used by: `web.app.create_app`, `cli.main._run_shared_host`
- Purpose: Walk a repository, build an in-memory graph, bulk-load it into KuzuDB
- Location: `src/axon/core/ingestion/pipeline.py` (`run_pipeline`, `reindex_files`)
- Phases executed in order (see "Ingestion Pipeline" section below)
- Depends on: all `core/ingestion/` modules, `core/graph/`, `core/parsers/`, `core/embeddings/`, `core/storage/`
- Used by: `cli.main.analyze`, `cli.main._initialize_writable_storage`
- Purpose: Dict-backed directed graph with O(1) lookups; secondary indexes on label, rel-type, and adjacency
- Location: `src/axon/core/graph/graph.py` (`KnowledgeGraph`), `src/axon/core/graph/model.py`
- Contains: `GraphNode`, `GraphRelationship`, `NodeLabel` enum, `RelType` enum, `generate_id`
- Used by: all ingestion phases, `KuzuBackend.load_graph()`, `KuzuBackend.bulk_load()`
- Purpose: Persist the graph to KuzuDB; provide search, traversal, and CRUD operations
- Location: `src/axon/core/storage/kuzu_backend.py` (`KuzuBackend`)
- Protocol: `src/axon/core/storage/base.py` (`StorageBackend`)
- Contains: schema creation, CSV bulk-load, BM25 FTS, fuzzy search, vector search, BFS traversal
- Used by: CLI commands, MCP server, Web routes
- Purpose: Expose code intelligence tools to AI agents over stdio (direct) or HTTP (shared-host mode)
- Location: `src/axon/mcp/server.py`, tool implementations in `src/axon/mcp/tools.py`
- Contains: 15 MCP tools, 3 MCP resources, stdio transport and streamable HTTP transport
- Depends on: `KuzuBackend`, `tools.py`, `resources.py`
- Used by: `cli.main.mcp`, `cli.main.serve`, `web.app.create_app` (HTTP mount)
- Purpose: FastAPI app serving REST API and (optionally) the compiled React SPA
- Location: `src/axon/web/app.py` (factory), `src/axon/web/routes/` (routers)
- Contains: 9 API routers, SSE event streaming, UI proxy mode, static file serving
- Depends on: `AxonRuntime`, `KuzuBackend`, `mcp.server.create_streamable_http_app`
- Used by: `cli.main.host`, `cli.main.ui`
- Purpose: React + TypeScript SPA for interactive graph visualization
- Location: `src/axon/web/frontend/src/`
- Built artifact served from: `src/axon/web/frontend/dist/`
- Communicates with: REST API at `/api/*` and SSE at `/api/events`
## Ingestion Pipeline
| Phase | Module | What it does |
|---|---|---|
| 1 | `walker.py` | Discover files via `git ls-files` (fallback: `os.walk`), read content with 8 threads |
| 2 | `structure.py` | Create `File` and `Folder` nodes; add `CONTAINS` edges |
| 3 | `parser_phase.py` | tree-sitter parse each file; emit `Function/Class/Method/Interface/TypeAlias/Enum` nodes + `DEFINES` edges |
| 4 | `imports.py` | Resolve import statements to file paths; add `IMPORTS` edges (parallel) |
| 5 | `calls.py` | Trace function/method calls to resolved symbols; add `CALLS` edges |
| 6 | `heritage.py` | Extract `EXTENDS`/`IMPLEMENTS` edges; patch `parent_class` on class nodes |
| 7 | `types.py` | Build `USES_TYPE` edges from type annotations |
| 8 | `community.py` | Leiden clustering over the call graph; create `COMMUNITY` nodes + `MEMBER_OF` edges |
| 9 | `processes.py` | Detect execution flows (entry-point → call chains); create `PROCESS` nodes + `STEP_IN_PROCESS` edges |
| 10 | `dead_code.py` | Mark symbols with no incoming `CALLS` edges as `is_dead=True` |
| 11 | `coupling.py` | Mine git log for file co-changes; add `COUPLED_WITH` edges |
## Data Flow
### Full Indexing (axon analyze .)
```
```
### MCP Tool Call (stdio, no --watch)
```
```
### MCP Tool Call (axon serve --watch, shared-host mode)
```
```
### File Watch Re-index
```
```
### Web/REST Query
```
```
## Entry Points
- Location: `src/axon/cli/main.py:567` (`analyze` command)
- Triggers: Full pipeline run and storage persistence
- Responsibilities: Initialize storage, run pipeline, write meta.json, register global registry
- Location: `src/axon/cli/main.py:821` (`host` command)
- Triggers: `_run_shared_host()` which starts uvicorn with FastAPI + MCP + file watcher
- Responsibilities: Single-process host serving UI, HTTP MCP, and watch mode together
- Location: `src/axon/cli/main.py:844` (`serve` command)
- Triggers: `_ensure_host_running()` → background `axon host --managed` + stdio-to-HTTP MCP proxy
- Responsibilities: Provides MCP stdio interface backed by a persistent shared host
- Location: `src/axon/cli/main.py:815` → `mcp.server.main()` (server.py:494)
- Triggers: `asyncio.run(mcp_main())` — pure stdio transport, no file watching
- Responsibilities: Stateless MCP server opening a fresh read-only KuzuBackend per call
- Location: `src/axon/cli/main.py:873` (`ui` command)
- Triggers: Either delegates to a running host, starts a UI proxy, or calls `_run_shared_host`
- Responsibilities: Open the React web UI in a browser
- Location: `src/axon/web/app.py:133`, created by `mcp.server.create_streamable_http_app()`
- Triggers: Mounted as a Starlette Route when `mount_mcp=True`
- Responsibilities: Serve MCP over StreamableHTTP for multi-session clients
## Key Design Patterns
## Error Handling
- Storage methods catch and log `Exception` with `logger.debug/warning` — search degradation instead of crash
- Embedding failure (`pipeline.py:230`): warning logged, run continues with FTS-only search
- Lock contention on `KuzuBackend.initialize()` retries with exponential backoff (`kuzu_backend.py:146`)
- Watcher global-phase failure re-queues dirty files and retries on next cycle (`watcher.py:282`)
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
