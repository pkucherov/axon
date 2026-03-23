# Codebase Concerns

**Analysis Date:** 2026-03-23

---

## High Priority

### 1. Missing Thread Safety on Write Paths in KuzuDB Backend

**Issue:** `add_nodes`, `add_relationships`, `remove_nodes_by_file`, and their delegates
`_insert_node` and `_insert_relationship` do not acquire `self._lock`. These methods are
called from the incremental reindex path while the watch loop runs on a background thread,
and the FastAPI reindex endpoint (`/api/reindex`) spawns an additional daemon thread.

**Files:**
- `src/axon/core/storage/kuzu_backend.py:179-205` (`add_nodes`, `add_relationships`, `remove_nodes_by_file`)
- `src/axon/core/storage/kuzu_backend.py:1077-1160` (`_insert_node`, `_insert_relationship`)
- `src/axon/web/routes/analysis.py:272-292` (daemon thread writes via reindex endpoint)

**Impact:** Concurrent writes to KuzuDB without a lock can silently corrupt the database or
produce partial writes. KuzuDB is an embedded database; it does not support concurrent writers
from multiple Python threads on the same `Connection` object without external serialization.

**Fix approach:** Acquire `self._lock` at the entry points of all write methods
(`add_nodes`, `add_relationships`, `remove_nodes_by_file`, `bulk_load`, `store_embeddings`,
`upsert_embeddings`).

---

### 2. `GET /api/graph` Loads the Entire Graph Into Memory On Every Request

**Issue:** `src/axon/web/routes/graph.py:52` calls `storage.load_graph()` on every HTTP
request to `/api/graph`. For large repos this deserializes every node and relationship from
KuzuDB into a `KnowledgeGraph` in-memory object and then serializes it again to JSON. There
is no caching, pagination, or limit.

**Files:**
- `src/axon/web/routes/graph.py:48-60`
- `src/axon/core/storage/kuzu_backend.py:743-807`

**Impact:** Memory spike proportional to graph size on every frontend graph-view open.
Blocks the request thread for several seconds on repos with tens of thousands of symbols.
Repeated calls from the frontend (e.g. polling) will degrade server responsiveness.

**Fix approach:** Add a server-side in-memory cache of the serialized graph (invalidated on
reindex), or implement pagination (`limit`/`offset` query params) and only load on demand.

---

### 3. Cypher Injection via String Interpolation (FTS and Multi-table Queries)

**Issue:** Several methods in `kuzu_backend.py` and `mcp/tools.py` build Cypher queries by
string-interpolating user-supplied values even when `escape_cypher()` is applied. The
`escape_cypher` helper (`src/axon/core/storage/kuzu_backend.py:83-92`) strips a small set of
metacharacters but is not a parameterized query and may be insufficient for all injection
patterns. The `QUERY_FTS_INDEX` stored procedure explicitly cannot use `$param` variables
(see NOTE at line 495), making this unavoidable for FTS — but the same interpolation pattern
is being used elsewhere where parameters would work.

**Files:**
- `src/axon/core/storage/kuzu_backend.py:493-542` (FTS — unavoidable, documented)
- `src/axon/mcp/tools.py:256-277` (`handle_context` heritage + imports queries)
- `src/axon/mcp/tools.py:432-435` (`handle_detect_changes` — guarded by `_SAFE_PATH`)
- `src/axon/mcp/tools.py:511-528` (`handle_coupling`)
- `src/axon/mcp/tools.py:643-648` (`handle_communities`)

**Impact:** An attacker who can control a symbol name or file path that contains Cypher
syntax not stripped by `escape_cypher` (e.g. backtick node labels, multi-statement syntax)
could enumerate or manipulate data. The web surface is localhost-only by default but is not
authenticated; the MCP surface is exposed to any MCP client.

**Fix approach:** Use parameterized `$variable` syntax wherever KuzuDB supports it (non-FTS
queries). For the FTS exception, the existing `escape_cypher` approach is documented. Audit
all `execute_raw` call sites (21 in `mcp/tools.py` alone) to confirm each escapes or
parameterizes its inputs.

---

### 4. No Authentication or Rate Limiting on the Web API

**Issue:** The FastAPI app (`src/axon/web/app.py`) has no authentication middleware. CORS is
restricted to `localhost` origins (`allow_origin_regex=r"https?://localhost(:\d+)?"`), but
this only prevents browser cross-origin requests — direct HTTP requests (curl, scripts, other
processes) are unrestricted. The `/api/reindex` endpoint (which triggers a full pipeline run)
and `/api/cypher` (arbitrary Cypher) are unprotected.

**Files:**
- `src/axon/web/app.py:114-120`
- `src/axon/web/routes/cypher.py:48-82`
- `src/axon/web/routes/analysis.py:246-292`

**Impact:** Any process on the same machine can trigger expensive re-indexing or run
arbitrary read queries. For a local dev tool this may be acceptable, but there is no opt-in
auth mechanism for team/server deployments.

**Fix approach:** Document the localhost-only deployment model explicitly. For server mode,
add optional token-based authentication middleware.

---

## Medium Priority

### 5. Broad `except Exception` Silently Discards Data-Loss Failures

**Issue:** The codebase uses `except Exception` + log/pass in many locations where a failure
means data is permanently lost or silently incomplete. In particular, `_insert_node` at
`kuzu_backend.py:1114` and `_insert_relationship` at `kuzu_backend.py:1157` swallow
insertion failures at DEBUG level. On a bulk load of 50 000 nodes, a systematic schema
mismatch would produce 50 000 silent drops with no user-visible error.

**Files:**
- `src/axon/core/storage/kuzu_backend.py:1112-1115` (node insert)
- `src/axon/core/storage/kuzu_backend.py:1155-1160` (relationship insert)
- `src/axon/core/storage/kuzu_backend.py:883-885, 964-965, 1012-1013` (cleanup, no logging)
- `src/axon/web/routes/files.py:77-78` (symbol count silently zeroed)

**Impact:** Partial graph state that is not detected by any health check. The `PipelineResult`
reports counts from the in-memory graph, not from what was actually persisted to KuzuDB, so
the user sees no discrepancy.

**Fix approach:** Promote insert failures to WARNING with a count. Surface a summary to the
CLI progress output. Add an optional integrity check comparing in-memory node count to
persisted count after `bulk_load`.

---

### 6. `load_graph()` Called Repeatedly in Watch Mode Global Phases

**Issue:** On every global-phase cycle (after `QUIET_PERIOD = 5.0s` of no file changes),
`_run_incremental_global_phases` in `src/axon/core/ingestion/watcher.py:149` calls
`storage.load_graph()` which re-reads all nodes and relationships from KuzuDB. This is the
same full-deserialization path as the web API concern above. For repos with thousands of
symbols this means several seconds of IO on every quiet period.

**Files:**
- `src/axon/core/ingestion/watcher.py:149`
- `src/axon/core/storage/kuzu_backend.py:743-807`

**Impact:** High CPU/IO on large repos during active editing sessions. The 5-second quiet
period is short enough that `load_graph` may be called dozens of times per hour.

**Fix approach:** Cache the in-memory graph between watch cycles. Invalidate the cache only
when file-local phases complete. Pass the cached graph directly to community/process/dead-code
phases rather than re-hydrating from storage.

---

### 7. Private Symbol Imported Across Module Boundaries

**Issue:** `src/axon/mcp/tools.py:20` imports the private function `_is_test_file` directly
from `src/axon/core/ingestion/dead_code.py`. This creates a cross-layer coupling from the MCP
tools layer into an implementation detail of the ingestion layer.

**Files:**
- `src/axon/mcp/tools.py:20`
- `src/axon/core/ingestion/dead_code.py:24-31`

**Impact:** Any refactoring of `dead_code.py` that renames or moves `_is_test_file` silently
breaks `test_impact` without type-checker warnings (since the import is a private name).

**Fix approach:** Expose `is_test_file` (without underscore prefix) from the `dead_code`
module, or move it to a shared utility module such as `src/axon/config/` or
`src/axon/core/ingestion/utils.py`.

---

### 8. Magic Numbers and Hardcoded Thresholds Throughout Ingestion

**Issue:** Several analysis thresholds are hardcoded module-level constants without
user-configurable paths:
- `coupling.py`: `since_months=6`, `min_cochanges=3`, `max_files_per_commit=50`, `min_strength=0.3`
- `watcher.py:39-43`: `QUIET_PERIOD = 5.0`, `MAX_DIRTY_AGE = 60.0`
- `watcher.py:128`: `_SMALL_CHANGE_THRESHOLD = 3`
- `processes.py:24`: `_MAX_FLOW_SIZE = 25`
- `embedder.py:65`: `_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"`

**Files:**
- `src/axon/core/ingestion/coupling.py:32-36, 98-103`
- `src/axon/core/ingestion/watcher.py:39-43, 128`
- `src/axon/core/ingestion/processes.py:24`
- `src/axon/core/embeddings/embedder.py:65`

**Impact:** Users indexing monorepos or repositories with different commit patterns cannot
tune false-positive rates or performance trade-offs without modifying source code.

**Fix approach:** Expose the key parameters through the CLI (`axon analyze --coupling-months`,
`--min-coupling-strength`) or a project-level `.axon/config.toml`.

---

### 9. Full Graph Re-Serialization on Every `/api/graph` Response

**Issue:** The `GET /api/graph` endpoint serializes every node and every relationship to a
Python dict list and returns it as a single JSON payload. For a 10 000-node graph this
produces a response payload of 5–15 MB. There is no `limit`/`offset`, no `depth` parameter,
and no streaming.

**Files:**
- `src/axon/web/routes/graph.py:47-60`

**Impact:** Browser frontend may freeze rendering a force-directed graph with tens of
thousands of nodes. Large JSON payloads strain the SSE/HTTP pipeline.

**Fix approach:** Add `limit` and `offset` query parameters. Consider a summary endpoint
that returns only structural stats or a filtered subgraph (by file, community, or label).

---

### 10. Dead Code Detection Does Not Cover TypeScript/JavaScript Symbols

**Issue:** `src/axon/core/ingestion/dead_code.py` processes `FUNCTION`, `METHOD`, and `CLASS`
node labels but the exemption logic (`_is_test_file`, `_is_python_public_api`,
decorator-based heuristics) is written entirely around Python conventions. TypeScript exported
symbols are partially handled via the `is_exported` flag, but test file detection only
recognises `tests/` directory paths — not `.spec.ts`, `.test.ts`, or `__tests__/` which are
standard TypeScript/Jest conventions.

**Files:**
- `src/axon/core/ingestion/dead_code.py:24-31` (`_is_test_file`)
- `src/axon/core/ingestion/dead_code.py:89-103` (`_is_exempt`)

**Impact:** TypeScript test helpers in `__tests__/` or `*.spec.ts` files are marked as dead
code, producing false positives in the dead code report.

**Fix approach:** Extend `_is_test_file` to recognise `__tests__/`, `*.spec.ts`, `*.test.ts`,
`*.spec.js`, `*.test.js`, `*.spec.tsx`, and `*.test.tsx` patterns.

---

## Low Priority

### 11. No File Size Limit on Ingested Source Files

**Issue:** `src/axon/core/ingestion/walker.py:92-104` reads every source file into memory via
`file_path.read_text(encoding="utf-8")` without a size guard. A generated file, vendor
bundle, or minified JS file that passes the extension check will be fully loaded and parsed by
tree-sitter.

**Files:**
- `src/axon/core/ingestion/walker.py:96`

**Impact:** Memory exhaustion or very long parse times if a 10 MB minified `.js` file is
present in the repository and not excluded by `.gitignore`.

**Fix approach:** Add a configurable `MAX_FILE_SIZE_BYTES` guard (e.g. 512 KB default) in
`read_file`, skipping and logging files that exceed it.

---

### 12. `handle_cycles` in MCP Tools Loads Full Graph On Demand

**Issue:** `src/axon/mcp/tools.py:1020` calls `storage.load_graph()` inside `handle_cycles`
every time the `cycles` MCP tool is invoked. This is a full in-memory graph hydration for
what is essentially a graph algorithm query.

**Files:**
- `src/axon/mcp/tools.py:1015-1061`

**Impact:** Slow response for the `cycles` MCP tool on large codebases. Repeated calls (e.g.
from an agent loop) each pay the full hydration cost.

**Fix approach:** Implement cycle detection directly via a Cypher query against KuzuDB, or
cache the igraph export between calls.

---

### 13. `escape_cypher` Is Incomplete as a Security Boundary

**Issue:** `src/axon/core/storage/kuzu_backend.py:83-92` removes `//`, `/* */`, `;`,
backtick-free comment syntax, and escapes backslashes and single quotes. However:
- Backtick-delimited identifiers (`` `label` ``) are not handled.
- Unicode homoglyphs and null-byte sequences (beyond `\x00`) are not checked.
- The function is intended only for the FTS path but has been reused in MCP tools as a
  general-purpose escaper, which may give false confidence.

**Files:**
- `src/axon/core/storage/kuzu_backend.py:83-92`
- `src/axon/mcp/tools.py:23` (imported as `_escape_cypher`)

**Impact:** Edge-case injection vectors remain. The risk is low because KuzuDB runs locally
with no network exposure in the default deployment.

**Fix approach:** Add a comment to `escape_cypher` explicitly stating it is only safe for
the FTS stored-procedure path. All other query construction should use `$param` syntax.

---

### 14. `reindex_files` (Incremental) Does Not Re-Run Global Phases

**Issue:** The docstring for `reindex_files` in `src/axon/core/ingestion/pipeline.py:253`
explicitly states that global phases (communities, processes, dead code, coupling) are NOT
re-run during an incremental reindex. These are only run during the full pipeline or by the
watcher's quiet-period trigger. If the user runs `axon analyze` (which does run global
phases), then uses the `/api/reindex` endpoint while not in watch mode, the global metadata
will be stale.

**Files:**
- `src/axon/core/ingestion/pipeline.py:241-340`
- `src/axon/web/routes/analysis.py:275-288` (calls `run_pipeline` — correct)

**Impact:** Communities, dead code flags, and coupling may not reflect the latest code after
an incremental reindex via the web UI if watch mode is not active.

**Fix approach:** Document this limitation clearly in the `/api/reindex` response body. The
web UI should indicate whether watch mode is active and warn users when global phases may be
stale.

---

### 15. No Test Coverage for MCP Server Transport and Streaming HTTP

**Issue:** `src/axon/mcp/server.py` (506 lines) is the MCP protocol surface. The test file
`tests/mcp/test_tools.py` covers tool handler logic but does not test the MCP server
transport layer (`create_streamable_http_app`, session lifecycle, `stdio_server` path).

**Files:**
- `src/axon/mcp/server.py`
- `tests/mcp/test_tools.py`

**Impact:** Regressions in MCP protocol handshake, session cleanup, or streaming behaviour
will not be caught by the test suite.

**Fix approach:** Add integration tests for the MCP HTTP transport using `httpx.AsyncClient`
against the streamable-HTTP app, covering tool invocation and session teardown.

---

### 16. No Coverage for Web Route Error Paths

**Issue:** `tests/web/test_routes.py` covers happy paths for most routes but does not test
storage failure injection — i.e. what the API returns when `storage.execute_raw` raises, when
`load_graph` raises, or when `repo_path` is `None` for the file-serving endpoint. The broad
`except Exception: pass` patterns in `files.py:77` and `graph.py:118-132` mean these paths
return empty/default data rather than errors, which is hard to distinguish from legitimate
empty results.

**Files:**
- `tests/web/test_routes.py`
- `src/axon/web/routes/files.py:65-78`
- `src/axon/web/routes/graph.py:117-132`

**Impact:** Broken-storage scenarios silently return partial data; this could mislead the
frontend (and AI agents using MCP) into treating a broken index as an empty one.

**Fix approach:** Add parameterized tests that mock `storage.execute_raw` to raise and verify
that routes return appropriate HTTP 500 responses rather than empty JSON.

---

*Concerns audit: 2026-03-23*
