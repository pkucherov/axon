# Codebase Structure

**Analysis Date:** 2026-03-23

## Directory Layout

```
axon/
├── src/
│   └── axon/                         # Main Python package
│       ├── __init__.py               # Package version (__version__)
│       ├── runtime.py                # AxonRuntime dataclass (shared host state)
│       ├── cli/
│       │   └── main.py               # Typer app, all CLI commands
│       ├── config/
│       │   ├── ignore.py             # .gitignore loading, DEFAULT_IGNORE_PATTERNS
│       │   └── languages.py          # File extension → language mapping
│       ├── core/
│       │   ├── cypher_guard.py       # Cypher injection prevention
│       │   ├── diff.py               # Branch structural comparison (diff_branches)
│       │   ├── embeddings/
│       │   │   ├── embedder.py       # embed_graph(), embed_nodes(), embed_query()
│       │   │   └── text.py           # Natural-language description generation for nodes
│       │   ├── graph/
│       │   │   ├── graph.py          # KnowledgeGraph (in-memory directed graph)
│       │   │   └── model.py          # GraphNode, GraphRelationship, NodeLabel, RelType
│       │   ├── ingestion/
│       │   │   ├── pipeline.py       # run_pipeline(), reindex_files(), build_graph()
│       │   │   ├── walker.py         # walk_repo(), discover_files(), read_file()
│       │   │   ├── watcher.py        # watch_repo() async loop (watchfiles)
│       │   │   ├── structure.py      # Phase 2: File/Folder nodes + CONTAINS edges
│       │   │   ├── parser_phase.py   # Phase 3: tree-sitter parsing → symbol nodes
│       │   │   ├── imports.py        # Phase 4: IMPORTS edges
│       │   │   ├── calls.py          # Phase 5: CALLS edges
│       │   │   ├── heritage.py       # Phase 6: EXTENDS/IMPLEMENTS edges
│       │   │   ├── types.py          # Phase 7: USES_TYPE edges
│       │   │   ├── community.py      # Phase 8: Leiden clustering → COMMUNITY nodes
│       │   │   ├── processes.py      # Phase 9: Execution flow → PROCESS nodes
│       │   │   ├── dead_code.py      # Phase 10: Dead code detection (is_dead flag)
│       │   │   ├── coupling.py       # Phase 11: Git co-change → COUPLED_WITH edges
│       │   │   ├── resolved.py       # ResolvedEdge dataclass (edge collection helper)
│       │   │   └── symbol_lookup.py  # build_name_index() helper
│       │   ├── parsers/
│       │   │   ├── base.py           # LanguageParser Protocol, ParseResult dataclass
│       │   │   ├── python_lang.py    # PythonParser (tree-sitter-python)
│       │   │   └── typescript.py     # TypeScriptParser (tree-sitter-typescript, tsx, js)
│       │   ├── search/
│       │   │   └── hybrid.py         # hybrid_search() via Reciprocal Rank Fusion
│       │   └── storage/
│       │       ├── base.py           # StorageBackend Protocol, SearchResult, NodeEmbedding
│       │       └── kuzu_backend.py   # KuzuBackend (KuzuDB implementation)
│       ├── mcp/
│       │   ├── server.py             # MCP Server, tool/resource registration, HTTP transport
│       │   ├── tools.py              # Tool handler functions (handle_query, handle_impact, …)
│       │   └── resources.py          # Resource handlers (get_overview, get_schema, …)
│       └── web/
│           ├── app.py                # create_app() factory, create_ui_proxy_app()
│           ├── routes/
│           │   ├── graph.py          # GET /api/graph, GET /api/graph/{id}
│           │   ├── search.py         # POST /api/search
│           │   ├── analysis.py       # Analysis endpoints (impact, context, communities)
│           │   ├── cypher.py         # POST /api/cypher
│           │   ├── diff.py           # POST /api/diff
│           │   ├── events.py         # GET /api/events (SSE stream)
│           │   ├── files.py          # GET /api/files, GET /api/files/{path}
│           │   ├── host.py           # GET /api/host (liveness check)
│           │   └── processes.py      # GET /api/processes
│           └── frontend/             # React + TypeScript SPA
│               ├── src/
│               │   ├── api/          # API client functions (axiosInstance, endpoints)
│               │   ├── components/
│               │   │   ├── graph/    # Force-directed graph canvas + animations
│               │   │   ├── explorer/ # File/symbol browser
│               │   │   ├── detail/   # Node detail panel
│               │   │   ├── analysis/ # Impact, community, coupling views
│               │   │   ├── cypher/   # Raw Cypher query editor
│               │   │   ├── layout/   # App shell, nav, sidebars
│               │   │   └── shared/   # Reusable UI primitives
│               │   ├── hooks/        # React hooks (useGraph, useSearch, …)
│               │   ├── stores/       # State management (Zustand stores)
│               │   ├── types/        # TypeScript type definitions
│               │   └── lib/          # Utility functions
│               └── dist/             # Compiled frontend (served as static files)
├── tests/                            # Test suite
├── pyproject.toml                    # Package metadata, dependencies, build config
└── .axon/                            # Per-repo index directory (gitignored)
    ├── kuzu/                         # KuzuDB database files
    ├── meta.json                     # Index stats and timestamp
    ├── host.json                     # Running host PID/URL metadata
    └── host-leases/                  # Lease files for managed host shutdown
```

---

## Directory Purposes

**`src/axon/cli/`:**
- Purpose: All user-facing CLI commands
- Key file: `main.py` — single file containing the entire Typer app, command handlers, host lifecycle helpers, and the `_run_shared_host()` orchestrator
- Add new commands here by decorating functions with `@app.command()`

**`src/axon/config/`:**
- Purpose: Configuration loading — language support and ignore patterns
- `languages.py`: maps file extensions to language strings used by parsers
- `ignore.py`: loads `.gitignore` rules and provides `should_ignore()` predicate
- Add new language support by updating `languages.py` and adding a parser in `core/parsers/`

**`src/axon/core/graph/`:**
- Purpose: The canonical in-memory data model
- `model.py` defines `NodeLabel`, `RelType`, `GraphNode`, `GraphRelationship`, and `generate_id()`
- `graph.py` provides `KnowledgeGraph` with secondary indexes for O(result) lookups
- Node IDs follow the format `{label}:{file_path}:{symbol_name}` (e.g., `function:src/app.py:main`)
- All ingestion phases, storage, and tools depend on these two files

**`src/axon/core/ingestion/`:**
- Purpose: The 11-phase ingestion pipeline and file-watch re-indexer
- Each phase module is independent; `pipeline.py` orchestrates them
- `watcher.py` runs as an async task alongside the uvicorn server in host mode
- `resolved.py` provides `ResolvedEdge` — a lightweight buffer for edge collection in parallel phases

**`src/axon/core/parsers/`:**
- Purpose: tree-sitter language parsers that emit structured symbol data
- `base.py` defines the `LanguageParser` protocol and `ParseResult`
- `python_lang.py` and `typescript.py` are the two concrete parsers
- Add new language support by implementing `LanguageParser` and registering in `parser_phase.py:_PARSER_FACTORIES`

**`src/axon/core/storage/`:**
- Purpose: Persistence layer abstraction + KuzuDB implementation
- `base.py` is the `StorageBackend` Protocol — depends only on `core/graph/`
- `kuzu_backend.py` is the 1248-line implementation; handles schema creation, CSV bulk-load, BM25 FTS indexes, vector search, BFS traversal, and incremental updates
- Open in read-only mode (`read_only=True`) for query-only access (MCP stdio mode)

**`src/axon/core/search/`:**
- Purpose: Hybrid search combining FTS and vector results
- `hybrid.py:hybrid_search()` applies Reciprocal Rank Fusion over BM25 + cosine results
- Falls back to fuzzy (Levenshtein) search when FTS returns no results

**`src/axon/core/embeddings/`:**
- Purpose: Local vector embedding generation using `fastembed`
- `embedder.py`: `embed_graph()` for full indexing, `embed_nodes()` for incremental updates, `embed_query()` for search-time encoding
- `text.py`: generates natural-language descriptions from `GraphNode` fields for embedding input
- Model is lazily loaded and cached thread-safely (`embedder.py:26`)

**`src/axon/mcp/`:**
- Purpose: Model Context Protocol server with 15 tools and 3 resources
- `server.py`: registers tools/resources, handles stdio and HTTP transports, routes calls to `tools.py`
- `tools.py`: stateless handler functions — each accepts `(storage, ...args)` and returns a string
- `resources.py`: MCP resources — `axon://overview`, `axon://dead-code`, `axon://schema`
- New tools: add to `tools.py`, register in `server.py:TOOLS` list, add dispatch case in `_dispatch_tool()`

**`src/axon/web/`:**
- Purpose: FastAPI REST API and bundled React frontend
- `app.py:create_app()` is the factory; accepts `runtime`, `mount_mcp`, `dev` flags
- `app.py:create_ui_proxy_app()` creates a lightweight proxy that forwards API calls to an existing host
- `routes/` contains one router per resource area, all mounted under `/api`
- Frontend communicates via REST + SSE (`/api/events` for live-update push)

**`src/axon/runtime.py`:**
- Purpose: Single shared-state container for the host process
- `AxonRuntime` dataclass holds: `storage`, `repo_path`, `watch`, `lock`, `host_url`, `mcp_url`, `owns_storage`, `event_listeners`
- Created once in `cli.main._run_shared_host()` and injected into both `web.app.create_app()` and `mcp.server.set_storage()`

---

## Key Files

| File | Purpose |
|---|---|
| `src/axon/cli/main.py` | All CLI commands; host lifecycle management (960 lines) |
| `src/axon/core/ingestion/pipeline.py` | Pipeline orchestrator — 11 phases (346 lines) |
| `src/axon/core/storage/kuzu_backend.py` | KuzuDB implementation — bulk load, FTS, vector search (1248 lines) |
| `src/axon/core/graph/graph.py` | In-memory graph with secondary indexes (161 lines) |
| `src/axon/core/graph/model.py` | Core data model — enums and dataclasses (99 lines) |
| `src/axon/core/ingestion/watcher.py` | File watch loop with debounced incremental reindex (287 lines) |
| `src/axon/mcp/server.py` | MCP server — 15 tools, 3 resources, dual transport (507 lines) |
| `src/axon/mcp/tools.py` | All MCP tool handler implementations |
| `src/axon/web/app.py` | FastAPI factory + UI proxy (215 lines) |
| `src/axon/core/storage/base.py` | `StorageBackend` Protocol (192 lines) |
| `src/axon/core/search/hybrid.py` | RRF hybrid search (100 lines) |

---

## Naming Conventions

**Files:**
- Python modules: `snake_case.py`
- Phase modules named after what they produce: `calls.py`, `heritage.py`, `community.py`

**Directories:**
- All lowercase: `cli/`, `core/`, `ingestion/`, `parsers/`, `storage/`

**Symbols:**
- Public handler functions in `tools.py`: `handle_{tool_name}(storage, ...)`
- Pipeline phase functions: `process_{phase_name}(data, graph)` or `resolve_{phase_name}(...)`
- FastAPI route files: one `router = APIRouter(tags=[...])` per file, one or more route functions

**Node IDs:** `{label.value}:{relative/file/path}:{symbol_name}`
- Example: `function:src/axon/cli/main.py:analyze`
- Example: `class:src/axon/core/graph/graph.py:KnowledgeGraph`
- Table lookup: `node_id.split(":", 1)[0]` → KuzuDB table name

---

## Where to Add New Code

**New CLI command:**
- Add `@app.command()` function in `src/axon/cli/main.py`
- For query-only commands, call `_load_storage()` to get read-only KuzuBackend
- Delegate logic to `mcp/tools.py` when the tool already exists

**New MCP tool:**
- Implement handler in `src/axon/mcp/tools.py` as `handle_{name}(storage, ...) -> str`
- Add `Tool(name="axon_{name}", ...)` to `TOOLS` list in `src/axon/mcp/server.py`
- Add dispatch branch in `_dispatch_tool()` in `src/axon/mcp/server.py`

**New REST endpoint:**
- Create or extend a file in `src/axon/web/routes/`
- Register `router` in `src/axon/web/app.py:create_app()` via `app.include_router()`
- Access `request.app.state.storage` and `request.app.state.runtime` in route handlers

**New ingestion phase:**
- Create `src/axon/core/ingestion/{phase_name}.py` with a `process_{phase_name}(data, graph)` function
- Import and call it at the appropriate step in `src/axon/core/ingestion/pipeline.py:run_pipeline()`
- If it produces nodes/relationships, add them to `PipelineResult` counts

**New language parser:**
- Implement `LanguageParser` protocol in `src/axon/core/parsers/{lang}.py`
- Register in `src/axon/core/ingestion/parser_phase.py:_PARSER_FACTORIES`
- Add extension mapping in `src/axon/config/languages.py`

**New graph node type:**
- Add entry to `NodeLabel` enum in `src/axon/core/graph/model.py`
- KuzuDB table created automatically from enum value in `kuzu_backend.py:_create_schema()`

---

## Special Directories

**`.axon/` (per-repo, in project root):**
- Purpose: Per-repository index storage
- Generated: Yes, by `axon analyze` / `axon host`
- Committed: No (should be in `.gitignore`)
- Contents: `kuzu/` database, `meta.json` stats, `host.json` process info, `host-leases/` lease files

**`~/.axon/` (global, in home directory):**
- Purpose: Global Axon data
- `~/.axon/repos/{slug}/meta.json`: Registry of all indexed repositories for `axon list`
- `~/.axon/update-check.json`: PyPI version check cache (24-hour TTL)

**`src/axon/web/frontend/dist/`:**
- Purpose: Compiled React SPA served as static files
- Generated: Yes, by `npm run build` in `src/axon/web/frontend/`
- Committed: Yes (included in Python package)

---

## Public API Surface

The following are the stable entry points for programmatic use:

**Pipeline:**
```python
from axon.core.ingestion.pipeline import run_pipeline, reindex_files, build_graph
graph, result = run_pipeline(repo_path, storage)   # full index
graph = build_graph(repo_path)                      # in-memory only, no storage
```

**Storage:**
```python
from axon.core.storage.kuzu_backend import KuzuBackend
backend = KuzuBackend()
backend.initialize(Path(".axon/kuzu"), read_only=True)
results = backend.fts_search("my_function", limit=10)
backend.close()
```

**Search:**
```python
from axon.core.search.hybrid import hybrid_search
from axon.core.embeddings.embedder import embed_query
results = hybrid_search(query, storage, query_embedding=embed_query(query))
```

**Web App:**
```python
from axon.web.app import create_app
app = create_app(db_path=Path(".axon/kuzu"), repo_path=Path("."), watch=False)
# Run with: uvicorn.run(app, host="127.0.0.1", port=8420)
```

**Graph Model:**
```python
from axon.core.graph.model import NodeLabel, RelType, generate_id, GraphNode, GraphRelationship
from axon.core.graph.graph import KnowledgeGraph
```

---

*Structure analysis: 2026-03-23*
