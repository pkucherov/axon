# Architecture

**Analysis Date:** 2026-03-23

## Pattern Overview

**Overall:** Pipeline-based graph ingestion with multi-surface query layer

Axon is a code intelligence engine that ingests source repositories into an
embedded graph database (KuzuDB) and exposes the resulting knowledge graph
through three query surfaces: a CLI, an MCP server, and a REST/WebSocket API
backing a React UI. A shared `AxonRuntime` container holds the singleton
storage connection when the full host is running, allowing all surfaces to
share one open database handle.

**Key Characteristics:**
- In-memory graph (`KnowledgeGraph`) built during ingestion, then bulk-loaded to KuzuDB
- Storage abstracted behind a `StorageBackend` Protocol — `KuzuBackend` is the only concrete implementation
- Incremental re-indexing driven by `watchfiles` with debounced global phases
- All three surfaces (CLI, MCP, Web) share the same `tools.py` handler functions
- Hybrid search (BM25 FTS + cosine-similarity vector) merged with Reciprocal Rank Fusion

---

## Layers

**CLI Layer:**
- Purpose: User-facing entry point; orchestrates all other subsystems
- Location: `src/axon/cli/main.py`
- Contains: `typer` app, command handlers, host/lifecycle management helpers
- Depends on: `ingestion.pipeline`, `storage.kuzu_backend`, `mcp.server`, `web.app`, `runtime`
- Used by: End-users and `axon serve --watch` (which re-invokes itself as a background subprocess)

**Runtime Container:**
- Purpose: Shared state for host processes; carries storage, repo path, watch flag, asyncio lock, and event listener list
- Location: `src/axon/runtime.py` (`AxonRuntime` dataclass)
- Depends on: `storage.base.StorageBackend`
- Used by: `web.app.create_app`, `cli.main._run_shared_host`

**Ingestion Pipeline:**
- Purpose: Walk a repository, build an in-memory graph, bulk-load it into KuzuDB
- Location: `src/axon/core/ingestion/pipeline.py` (`run_pipeline`, `reindex_files`)
- Phases executed in order (see "Ingestion Pipeline" section below)
- Depends on: all `core/ingestion/` modules, `core/graph/`, `core/parsers/`, `core/embeddings/`, `core/storage/`
- Used by: `cli.main.analyze`, `cli.main._initialize_writable_storage`

**Graph Model (in-memory):**
- Purpose: Dict-backed directed graph with O(1) lookups; secondary indexes on label, rel-type, and adjacency
- Location: `src/axon/core/graph/graph.py` (`KnowledgeGraph`), `src/axon/core/graph/model.py`
- Contains: `GraphNode`, `GraphRelationship`, `NodeLabel` enum, `RelType` enum, `generate_id`
- Used by: all ingestion phases, `KuzuBackend.load_graph()`, `KuzuBackend.bulk_load()`

**Storage Backend:**
- Purpose: Persist the graph to KuzuDB; provide search, traversal, and CRUD operations
- Location: `src/axon/core/storage/kuzu_backend.py` (`KuzuBackend`)
- Protocol: `src/axon/core/storage/base.py` (`StorageBackend`)
- Contains: schema creation, CSV bulk-load, BM25 FTS, fuzzy search, vector search, BFS traversal
- Used by: CLI commands, MCP server, Web routes

**MCP Server:**
- Purpose: Expose code intelligence tools to AI agents over stdio (direct) or HTTP (shared-host mode)
- Location: `src/axon/mcp/server.py`, tool implementations in `src/axon/mcp/tools.py`
- Contains: 15 MCP tools, 3 MCP resources, stdio transport and streamable HTTP transport
- Depends on: `KuzuBackend`, `tools.py`, `resources.py`
- Used by: `cli.main.mcp`, `cli.main.serve`, `web.app.create_app` (HTTP mount)

**Web Layer:**
- Purpose: FastAPI app serving REST API and (optionally) the compiled React SPA
- Location: `src/axon/web/app.py` (factory), `src/axon/web/routes/` (routers)
- Contains: 9 API routers, SSE event streaming, UI proxy mode, static file serving
- Depends on: `AxonRuntime`, `KuzuBackend`, `mcp.server.create_streamable_http_app`
- Used by: `cli.main.host`, `cli.main.ui`

**Frontend:**
- Purpose: React + TypeScript SPA for interactive graph visualization
- Location: `src/axon/web/frontend/src/`
- Built artifact served from: `src/axon/web/frontend/dist/`
- Communicates with: REST API at `/api/*` and SSE at `/api/events`

---

## Ingestion Pipeline

`src/axon/core/ingestion/pipeline.py:run_pipeline` executes phases 1–11 in sequence:

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

After all phases: `storage.bulk_load(graph)` then `embed_graph(graph)` (fastembed local model).

Phases 5, 6, 7 run concurrently inside a `ThreadPoolExecutor(max_workers=3)`.
Phase 11 runs concurrently with phases 8–10 in a separate `ThreadPoolExecutor(max_workers=1)`.

---

## Data Flow

### Full Indexing (axon analyze .)

```
User runs: axon analyze <path>
  → cli.main.analyze (main.py:567)
    → KuzuBackend().initialize(db_path)           # open/create .axon/kuzu
    → run_pipeline(repo_path, storage)             # pipeline.py:90
        → walk_repo()  →  [FileEntry, ...]         # walker.py
        → KnowledgeGraph()                         # graph.py
        → process_structure()                      # structure.py
        → process_parsing()  →  ParseData          # parser_phase.py (tree-sitter)
        → process_imports()                        # imports.py (parallel)
        → [calls/heritage/types] concurrently      # ThreadPoolExecutor
        → process_communities()                    # community.py (Leiden)
        → process_processes()                      # processes.py
        → process_dead_code()                      # dead_code.py
        → coupling_future.result()                 # coupling.py (git log)
        → storage.bulk_load(graph)                 # kuzu_backend.py:874
        → embed_graph(graph) → storage.store_embeddings()  # embedder.py
    → write .axon/meta.json
    → _register_in_global_registry()              # writes ~/.axon/repos/<slug>/meta.json
    → storage.close()
```

### MCP Tool Call (stdio, no --watch)

```
AI agent sends MCP request
  → mcp.server.call_tool(name, arguments)          # server.py:443
    → _with_storage(fn)                            # server.py:101
        → _open_storage()  →  read-only KuzuBackend  # short-lived connection
        → _dispatch_tool(name, arguments, storage) # server.py:394
            → tools.handle_*(storage, ...)         # tools.py
                → hybrid_search() / traverse() / ...
    → TextContent(text=result)
```

### MCP Tool Call (axon serve --watch, shared-host mode)

```
axon serve --watch (client process)
  → _ensure_host_running(...)                     # spawns background host if needed
  → _proxy_stdio_to_http_mcp(mcp_url)             # bridges stdio ↔ HTTP MCP
      → streamablehttp_client(mcp_url)

Background host (axon host --managed)
  → AxonRuntime(storage, lock, ...)
  → web.app.create_app(mount_mcp=True)
  → Route("/mcp", StreamableHTTPASGIApp)           # server.py:500
  → watch_repo() running as concurrent asyncio task  # watcher.py
```

### File Watch Re-index

```
watchfiles detects file change  (watcher.py:233)
  → _reindex_files(changed_paths)                 # immediate, file-local only
      → reindex_files(entries, storage)           # pipeline.py:241
          → storage.remove_nodes_by_file()        # kuzu_backend.py:187
          → process_structure/parsing/imports/calls/heritage/types
          → storage.add_nodes(); storage.add_relationships()
  after QUIET_PERIOD=5s with no new changes:
  → _run_incremental_global_phases()
      → storage.load_graph() → KnowledgeGraph     # hydrate full graph
      → process_communities/processes/dead_code   # (skipped for small changes)
      → storage.update_dead_flags()
      → embed_nodes(dirty_node_ids)
      → storage.rebuild_fts_indexes()
  if new git commit detected → process_coupling()
```

### Web/REST Query

```
Browser → POST /api/search
  → web.routes.search.search(body, request)       # search.py:26
    → embed_query(body.query)                     # embedder.py
    → hybrid_search(query, storage, query_embedding)  # hybrid.py:20
        → storage.fts_search(query, limit)        # BM25 via KuzuDB FTS extension
        → storage.vector_search(embedding, limit) # cosine similarity in Cypher
        → RRF merge
    → JSON response
```

---

## Entry Points

**`axon analyze`:**
- Location: `src/axon/cli/main.py:567` (`analyze` command)
- Triggers: Full pipeline run and storage persistence
- Responsibilities: Initialize storage, run pipeline, write meta.json, register global registry

**`axon host`:**
- Location: `src/axon/cli/main.py:821` (`host` command)
- Triggers: `_run_shared_host()` which starts uvicorn with FastAPI + MCP + file watcher
- Responsibilities: Single-process host serving UI, HTTP MCP, and watch mode together

**`axon serve --watch`:**
- Location: `src/axon/cli/main.py:844` (`serve` command)
- Triggers: `_ensure_host_running()` → background `axon host --managed` + stdio-to-HTTP MCP proxy
- Responsibilities: Provides MCP stdio interface backed by a persistent shared host

**`axon mcp`:**
- Location: `src/axon/cli/main.py:815` → `mcp.server.main()` (server.py:494)
- Triggers: `asyncio.run(mcp_main())` — pure stdio transport, no file watching
- Responsibilities: Stateless MCP server opening a fresh read-only KuzuBackend per call

**`axon ui`:**
- Location: `src/axon/cli/main.py:873` (`ui` command)
- Triggers: Either delegates to a running host, starts a UI proxy, or calls `_run_shared_host`
- Responsibilities: Open the React web UI in a browser

**MCP HTTP endpoint (`/mcp`):**
- Location: `src/axon/web/app.py:133`, created by `mcp.server.create_streamable_http_app()`
- Triggers: Mounted as a Starlette Route when `mount_mcp=True`
- Responsibilities: Serve MCP over StreamableHTTP for multi-session clients

---

## Key Design Patterns

**Protocol-backed Storage Abstraction:**
`StorageBackend` (`src/axon/core/storage/base.py`) is a `runtime_checkable` Protocol with 25 methods.
`KuzuBackend` is the sole implementation. This enables in-memory graph snapshots (`build_graph()`) and branch diffing (`diff_branches`) without touching the database.

**Two-phase In-memory Graph:**
All ingestion phases operate on a `KnowledgeGraph` (pure dicts, no I/O). After all phases complete, `storage.bulk_load(graph)` flushes to KuzuDB via CSV COPY FROM (falls back to individual INSERT on error). This keeps ingestion fast and atomic.

**Shared Host / Lease System:**
Multiple `axon serve` processes share one background `axon host --managed` process. Leases (`~/.axon/kuzu/host-leases/`) track active clients. The managed host exits when all leases expire and the idle period exceeds 2 seconds (`main.py:544`).

**Deterministic Node IDs:**
`generate_id(label, file_path, symbol_name)` in `model.py:44` produces IDs of the form `function:src/app.py:my_func`. KuzuDB tables use this string as the `PRIMARY KEY`, enabling idempotent upserts and stable references across re-indexing.

**Single `CodeRelation` Relationship Table Group:**
All relationship types (`CALLS`, `IMPORTS`, `CONTAINS`, etc.) share one KuzuDB REL TABLE GROUP named `CodeRelation` with a `rel_type STRING` discriminator column (`kuzu_backend.py:1043`). This allows cross-type Cypher queries without union scans.

---

## Error Handling

**Strategy:** Errors in individual phases are logged and swallowed where safe (e.g., FTS index rebuild failure); hard failures propagate upward.

**Patterns:**
- Storage methods catch and log `Exception` with `logger.debug/warning` — search degradation instead of crash
- Embedding failure (`pipeline.py:230`): warning logged, run continues with FTS-only search
- Lock contention on `KuzuBackend.initialize()` retries with exponential backoff (`kuzu_backend.py:146`)
- Watcher global-phase failure re-queues dirty files and retries on next cycle (`watcher.py:282`)

---

## Cross-Cutting Concerns

**Locking:** `asyncio.Lock` in `AxonRuntime` serializes write operations between the file watcher and MCP/API reads. `KuzuBackend._lock` (`threading.Lock`) protects the KuzuDB connection from concurrent thread access.

**Cypher Injection Guard:** `src/axon/core/cypher_guard.py` (`sanitize_cypher`, `WRITE_KEYWORDS`) validates raw Cypher before execution via `axon_cypher` tool. `escape_cypher()` in `kuzu_backend.py:83` sanitizes FTS query strings that cannot use parameterized queries.

**Node ID Convention:** `{label}:{file_path}:{symbol_name}` — table lookup derives the KuzuDB table name from the prefix (`kuzu_backend.py:104`).

**Language Support:** `src/axon/config/languages.py` drives file filtering. Parsers exist for Python, TypeScript, TSX, and JavaScript (`parser_phase.py:43`).

---

*Architecture analysis: 2026-03-23*
