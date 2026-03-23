# External Integrations

**Analysis Date:** 2026-03-23

## APIs & External Services

**PyPI (version check):**
- Service: PyPI JSON API
- Purpose: Check for newer versions of `axoniq` on startup
- Endpoint: `https://pypi.org/pypi/axoniq/json` (defined as `UPDATE_CHECK_URL` in `src/axon/cli/main.py`)
- Auth: None (public API)
- Caching: Result cached in `~/.axon/update-check.json`; checked at most once per 24 hours
- Skipped for: `mcp`, `serve`, `host` commands

**No other external APIs.** Axon is intentionally offline-first — embeddings run locally via fastembed, graph storage is embedded KuzuDB, and no cloud services are required for core functionality.

## Data Storage

**Databases:**
- KuzuDB (embedded graph database)
  - Type: Embedded property graph; no server process
  - Location: `.axon/kuzu/` within the indexed repository root
  - Client: `kuzu` Python package >=0.11.0
  - Schema: Node tables per `NodeLabel` enum + a single `CodeRelation` relationship table group
  - Implementation: `src/axon/core/storage/kuzu_backend.py`
  - Thread safety: `threading.Lock` guards all `conn.execute()` calls
  - Read-only mode: Used by MCP server and web server to avoid blocking the writer
  - FTS: KuzuDB's built-in FTS extension (BM25) indexed on `name`, `content`, `signature`
  - Vector search: Native `array_cosine_similarity` Cypher function; vectors stored in `Embedding` node table

**File Storage:**
- Local filesystem only
- Index stored in `.axon/kuzu/` (per-repo)
- Update cache stored in `~/.axon/update-check.json` (per-user)
- No cloud file storage

**Caching:**
- Embedding model cache: fastembed downloads and caches model weights to the OS default cache directory on first use
- KuzuDB acts as the persistent result cache for all graph data

## Authentication & Identity

**Auth Provider:** None

- No authentication on the web server or MCP server
- The web server adds a CORS middleware scoped to `localhost` only: `allow_origin_regex = r"https?://localhost(:\d+)?"`
  - Configured in `src/axon/web/app.py`
- The tool is designed to run locally; no user accounts, tokens, or sessions

## MCP Protocol Integration

**Model Context Protocol (MCP):**
- SDK: `mcp >= 1.0.0`
- Transport 1: stdio — primary mode for AI agents (`src/axon/mcp/server.py`, `asyncio.run(main())`)
- Transport 2: Streamable HTTP ASGI — optional, mounted at `/mcp` route when `--mount-mcp` flag is used
  - Uses `StreamableHTTPSessionManager` and `StreamableHTTPASGIApp` from `mcp.server`
- Server name: `"axon"` (`mcp.server.Server("axon")`)

**Exposed Tools (15 total):**
| Tool | Purpose |
|------|---------|
| `axon_list_repos` | List indexed repositories |
| `axon_query` | Hybrid keyword + vector search |
| `axon_context` | 360-degree symbol view (callers, callees, types, community) |
| `axon_impact` | Blast radius analysis via BFS on CALLS edges |
| `axon_dead_code` | List unreachable symbols |
| `axon_detect_changes` | Map git diff lines to affected symbols |
| `axon_cypher` | Execute raw Cypher against KuzuDB |
| `axon_coupling` | Temporal coupling from git co-change patterns |
| `axon_communities` | List/drill Leiden community clusters |
| `axon_explain` | Narrative summary of a symbol's role |
| `axon_review_risk` | PR risk scoring from git diff |
| `axon_call_path` | BFS shortest call chain between two symbols |
| `axon_file_context` | All context for a file in one call |
| `axon_test_impact` | Find tests affected by changes |
| `axon_cycles` | Circular dependency detection (SCC analysis) |

**Exposed Resources (3 total):**
- `axon://overview` — codebase statistics
- `axon://dead-code` — dead code report
- `axon://schema` — graph schema description

## Web API Integration

**FastAPI REST API** — all routes prefixed `/api/`:
- `GET  /api/graph` — full graph nodes and edges
- `GET  /api/node/{id}` — single node context
- `GET  /api/overview` — codebase stats
- `POST /api/search` — hybrid search
- `GET  /api/impact/{nodeId}` — blast radius
- `GET  /api/dead-code` — dead code report
- `GET  /api/coupling` — file coupling pairs
- `GET  /api/communities` — community clusters
- `GET  /api/processes` — process flows
- `GET  /api/health` — health score
- `GET  /api/tree` — file tree
- `GET  /api/file` — file content (by `?path=...`)
- `POST /api/cypher` — raw Cypher execution
- `POST /api/diff` — branch comparison
- `POST /api/reindex` — trigger incremental re-index
- `GET  /api/events` — SSE event stream (reindex_start, reindex_complete, file_changed)

**Server-Sent Events (SSE):**
- Library: `sse-starlette >= 2.0.0`
- Endpoint: `GET /api/events`
- Pattern: Per-client `asyncio.Queue`; fan-out to all connected clients
- Keepalive: 30-second timeout comment sent to prevent connection drop
- Implementation: `src/axon/web/routes/events.py`

**Frontend HTTP Client:**
- Library: `ky 1.7.0` (fetch wrapper)
- Base URL: `/api` (relative, assumes same-origin)
- Timeout: 30,000ms
- Implementation: `src/axon/web/frontend/src/api/client.ts`

## Tree-sitter Language Grammars

**Python grammar:**
- Package: `tree-sitter-python >= 0.23.0`
- Usage: `import tree_sitter_python as tspython` in `src/axon/core/parsers/python_lang.py`
- Parses: functions, classes, methods, imports, calls, type annotations, inheritance

**JavaScript grammar:**
- Package: `tree-sitter-javascript >= 0.23.0`
- Usage: `import tree_sitter_javascript as tsjavascript` in `src/axon/core/parsers/typescript.py`
- Parses: ES module files (.js, .mjs, .cjs, .jsx)

**TypeScript grammar:**
- Package: `tree-sitter-typescript >= 0.23.0`
- Usage: `import tree_sitter_typescript as tstypescript` in `src/axon/core/parsers/typescript.py`
- Provides: `language_typescript()` for .ts files and `language_tsx()` for .tsx files

## Embedding Model Integration

**fastembed:**
- Package: `fastembed >= 0.7.0`
- Model: `BAAI/bge-small-en-v1.5` (default, hardcoded in `src/axon/core/embeddings/embedder.py`)
- Runtime: Fully local; model weights downloaded to OS cache on first run
- No API key or network call at query time
- Thread-safe model cache: module-level `_model_cache` dict protected by `threading.Lock`
- Batch size: 64 (configurable)
- Used for: generating node embeddings during ingestion; embedding queries for vector search

## Graph Analytics Integration

**igraph + leidenalg:**
- `igraph >= 1.0.0` — in-memory graph operations
- `leidenalg >= 0.11.0` — Leiden community detection
- Integration point: `src/axon/core/ingestion/community.py`
- Pattern: Export KnowledgeGraph to igraph, run Leiden algorithm, write Community nodes and `BELONGS_TO` edges back into KuzuDB
- Edge weighting: CALLS = 1.0, EXTENDS/IMPLEMENTS/USES_TYPE = 0.5

## Git Integration

**subprocess (stdlib):**
- Used in `src/axon/core/ingestion/coupling.py` to run `git log` for temporal coupling analysis
- Used in `src/axon/core/ingestion/watcher.py` to track HEAD SHA for commit-triggered coupling re-runs
- Used in `src/axon/core/diff.py` for branch comparison
- No git library dependency — raw subprocess calls to system `git`
- Requires `git` to be available on PATH; gracefully skips coupling if not in a git repo

## File System Watching

**watchfiles:**
- Package: `watchfiles >= 1.0.0` (Rust-backed)
- Usage: `src/axon/core/ingestion/watcher.py`
- Poll interval: 500ms
- Debounce: Global phases fire after 5.0s quiet period (no changes)
- Max dirty age: 60s (prevents starvation under continuous writes)

## CI/CD & Deployment

**Hosting:**
- Python package: PyPI (package name `axoniq`)
- No container images or cloud hosting defined in the repository

**CI Pipeline:**
- Platform: GitHub Actions
- Workflows:
  - `.github/workflows/publish.yml` — triggered on `v*` tags; runs tests, builds frontend, builds wheel, publishes to PyPI using OIDC trusted publishing (no API token stored)
  - `.github/workflows/pr-check.yml` — verifies linked issue in PR description
- Python version in CI: 3.11 (via `astral-sh/setup-uv@v5`)
- Node version in CI: 20 (via `actions/setup-node@v4`)
- Build steps: `npm ci && npm run build` (frontend), then `uv build --sdist` + `uv build --wheel`
- Wheel verification: checks that the wheel contains at least 10 Python source files

## Optional Neo4j Backend

**neo4j:**
- Package: `neo4j >= 5.0.0` (optional, `pyproject.toml [project.optional-dependencies] neo4j`)
- Install: `pip install axoniq[neo4j]`
- Status: Declared as optional dependency; KuzuDB is the active default backend
- Not referenced in any source file found — may be a planned or legacy integration

## Webhooks & Callbacks

**Incoming:** None — no webhook endpoints defined

**Outgoing:** None — only outbound HTTP is the version check to `https://pypi.org/pypi/axoniq/json`

## Environment Configuration

**Required env vars:** None — all configuration is via CLI flags or defaults

**Optional/notable paths:**
- `.axon/kuzu/` — KuzuDB database directory (inside the indexed repository)
- `~/.axon/update-check.json` — cached version check result
- `.axonignore` or `.gitignore` — file exclusion patterns respected by the ingestion walker (`src/axon/config/ignore.py`)

---

*Integration audit: 2026-03-23*
