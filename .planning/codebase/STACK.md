# Technology Stack

**Analysis Date:** 2026-03-23

## Languages

**Primary:**
- Python 3.11 — entire backend, CLI, MCP server, ingestion pipeline, graph storage
  - Pinned to 3.11 via `.python-version`; `pyproject.toml` allows >=3.11 (supports 3.11, 3.12, 3.13)
- TypeScript 5.6 — frontend SPA in `src/axon/web/frontend/src/`

**Secondary:**
- JavaScript (ES modules) — Vite config, test harness glue
- TSX — React component files under `src/axon/web/frontend/src/components/`

## Runtime

**Environment:**
- Python runtime: CPython 3.11 (pinned via `.python-version`)
- Node.js: 20 (used in CI for frontend build; version from `.github/workflows/publish.yml`)
- The shipped wheel embeds a pre-built frontend dist — no Node required at install time

**Package Manager:**
- Python: `uv` (used in CI via `astral-sh/setup-uv`; `hatchling` is the build backend)
- Frontend: `npm` — lockfile at `src/axon/web/frontend/package-lock.json`
- Lockfile: `package-lock.json` present; no Python lockfile committed (uv generates on sync)

## Frameworks

**Core (Python):**
- `typer >= 0.15.0` — CLI framework; entry point `axon.cli.main:app`
- `fastapi >= 0.115.0` — Web API framework; app factory in `src/axon/web/app.py`
- `uvicorn[standard] >= 0.34.0` — ASGI server; launched from CLI `axon serve` command
- `mcp >= 1.0.0` — Model Context Protocol SDK; MCP server in `src/axon/mcp/server.py`
- `sse-starlette >= 2.0.0` — SSE streaming middleware; used in `src/axon/web/routes/events.py`

**Frontend:**
- React 18.3 — UI framework; SPA entry in `src/axon/web/frontend/src/App.tsx`
- Tailwind CSS 4.0 — utility CSS; configured via `@tailwindcss/vite` plugin
- Vite 6.0 — build tool and dev server; config at `src/axon/web/frontend/vite.config.ts`

**Testing:**
- `pytest >= 8.0.0` — test runner
- `pytest-asyncio >= 0.24.0` — async test support; `asyncio_mode = "auto"` in `pyproject.toml`
- `pytest-cov >= 6.0.0` — coverage reporting
- Tests in `tests/` with subdirectories `cli/`, `core/`, `e2e/`, `mcp/`, `web/`

**Build/Dev:**
- `hatchling` — Python wheel build backend; configured in `pyproject.toml [build-system]`
- `ruff >= 0.9.0` — linter and formatter; target `py311`, line length 100
  - Rules enabled: E (pycodestyle), F (pyflakes), I (isort), N (pep8-naming), W (warnings)

## Key Dependencies

**Graph Database:**
- `kuzu >= 0.11.0` — embedded property graph database with Cypher query support
  - Single dependency for graph persistence; no separate DB server needed
  - Stores code nodes and relationships in `.axon/kuzu/` inside the indexed repo
  - Uses KuzuDB FTS extension for BM25 full-text search (`src/axon/core/storage/kuzu_backend.py`)
  - Cosine similarity vector search via native `array_cosine_similarity` Cypher function

**Parsing:**
- `tree-sitter >= 0.25.0` — core parser library (Rust-backed)
- `tree-sitter-python >= 0.23.0` — Python grammar; used in `src/axon/core/parsers/python_lang.py`
- `tree-sitter-javascript >= 0.23.0` — JavaScript grammar; used in `src/axon/core/parsers/typescript.py`
- `tree-sitter-typescript >= 0.23.0` — TypeScript/TSX grammar; used in `src/axon/core/parsers/typescript.py`

**Embeddings:**
- `fastembed >= 0.7.0` — local embedding model runner; no external API call required
  - Default model: `BAAI/bge-small-en-v1.5` (downloaded to local cache on first use)
  - Used in `src/axon/core/embeddings/embedder.py`

**Graph Analytics:**
- `igraph >= 1.0.0` — in-memory graph library for community detection algorithms
- `leidenalg >= 0.11.0` — Leiden community detection algorithm; used in `src/axon/core/ingestion/community.py`
  - Runs on the call + heritage subgraph to partition code into logical communities

**File Watching:**
- `watchfiles >= 1.0.0` — Rust-backed file system watcher; used in `src/axon/core/ingestion/watcher.py`
  - Monitors file changes with 500ms poll interval; triggers incremental re-indexing

**Utilities:**
- `rich >= 13.0.0` — terminal output formatting; progress bars, styled console output in CLI
- `pathspec >= 1.0.4` — gitignore pattern matching; used in `src/axon/config/ignore.py`
- `anyio` — async compatibility layer; used in CLI for async execution

**Optional:**
- `neo4j >= 5.0.0` — optional alternative graph backend (`pyproject.toml [project.optional-dependencies] neo4j`)
  - Not used in default install; KuzuDB is the default

## Frontend Key Dependencies

**Graph Visualization:**
- `graphology 0.25.4` — directed graph data structure
- `graphology-layout-forceatlas2 0.10.1` — ForceAtlas2 layout algorithm
- `graphology-layout-noverlap 0.4.2` — overlap removal layout
- `sigma 3.0.0` — WebGL graph renderer; custom canvas renderer implemented in `src/axon/web/frontend/src/components/graph/GraphCanvas.tsx`
  - Note: Sigma is imported as a dependency but the canvas uses a custom WebGL-free renderer

**State Management:**
- `zustand 5.0.0` — lightweight React state management
  - Stores: `graphStore.ts`, `dataStore.ts`, `viewStore.ts`

**HTTP Client:**
- `ky 1.7.0` — fetch-based HTTP client; used in `src/axon/web/frontend/src/api/client.ts`

**UI Components:**
- `cmdk 1.0.0` — command palette component
- `lucide-react 0.460.0` — icon library
- `class-variance-authority 0.7.1` + `tailwind-merge 2.6.0` + `clsx 2.1.1` — class name utilities

**Code Display:**
- `shiki 1.0.0` — syntax highlighting (code view panel)
- `dompurify 3.3.1` — HTML sanitization

## Configuration

**Environment:**
- No required environment variables for core functionality
- Database path defaults to `.axon/kuzu/` in the current working directory
- `.env` file presence noted but contents not read

**Build:**
- `pyproject.toml` — Python project config, dependencies, ruff rules, pytest settings
- `src/axon/web/frontend/package.json` — frontend dependencies
- `src/axon/web/frontend/vite.config.ts` — Vite build configuration (TypeScript)
- Frontend built into `src/axon/web/frontend/dist/` and bundled into the Python wheel
  via `[tool.hatch.build] artifacts` in `pyproject.toml`

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 20 (for frontend development only)
- Git (required for coupling analysis — `subprocess.run(["git", "log", ...])` in `src/axon/core/ingestion/coupling.py`)
- No Docker required; everything runs in-process

**Production:**
- Single `pip install axoniq` installs the complete stack
- Distributed as a wheel on PyPI (package name: `axoniq`)
- Default port: 8420 (web server), 8421 (managed/host mode)

---

*Stack analysis: 2026-03-23*
