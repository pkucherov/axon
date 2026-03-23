# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Files:**
- Source modules use `snake_case.py` (e.g., `kuzu_backend.py`, `parser_phase.py`, `dead_code.py`)
- Test files are prefixed `test_` and mirror the module name (e.g., `test_kuzu_backend.py`, `test_parser_python.py`)
- `__init__.py` files are present in every package but are usually empty or contain re-exports only

**Functions:**
- Public functions use `snake_case` (e.g., `run_pipeline`, `walk_repo`, `process_imports`)
- Private/internal helpers are prefixed with a single underscore: `_load_storage`, `_build_meta`, `_fetch_latest_version`
- Ingestion phase functions follow the pattern `process_<noun>` (e.g., `process_calls`, `process_communities`, `process_dead_code`)
- Parser extraction methods follow `_extract_*` per the CONTRIBUTING.md guidance

**Classes:**
- `PascalCase` throughout (e.g., `KuzuBackend`, `PipelineResult`, `AxonRuntime`, `LanguageParser`)
- Dataclasses used extensively for data containers: `GraphNode`, `GraphRelationship`, `FileEntry`, `SymbolInfo`, `ParseResult`
- Abstract base classes use the `ABC` mixin directly (e.g., `LanguageParser(ABC)`)

**Variables:**
- `snake_case` for local variables and instance attributes
- Module-level constants are `UPPER_SNAKE_CASE` (e.g., `DEFAULT_HOST`, `DEFAULT_PORT`, `UPDATE_CHECK_URL`, `_NODE_PROPERTIES`)
- Private module-level constants prefixed with underscore: `_SYMBOL_LABELS`, `_LABEL_MAP`, `_NODE_TABLE_NAMES`

**Enums:**
- Enum members are `UPPER_SNAKE_CASE` (e.g., `NodeLabel.FILE`, `RelType.COUPLED_WITH`, `NodeLabel.TYPE_ALIAS`)
- Enum values are lowercase strings matching the graph/database representation (e.g., `"file"`, `"type_alias"`)

## Code Style

**Formatter:** `ruff format` — enforced in CI and required before PR

**Linter:** `ruff check` with `select = ["E", "F", "I", "N", "W"]`
- `E` — pycodestyle errors
- `F` — pyflakes
- `I` — isort (import ordering)
- `N` — pep8-naming
- `W` — pycodestyle warnings

**Line length:** 100 characters (`line-length = 100` in `pyproject.toml`)

**Target version:** Python 3.11+ (`target-version = "py311"`)

## Import Organization

Every source file begins with `from __future__ import annotations` to enable PEP 563 postponed evaluation of annotations. This is universal across the codebase.

**Order (enforced by ruff/isort):**
1. `from __future__ import annotations`
2. Standard library imports (alphabetical)
3. Third-party imports (alphabetical)
4. Local `axon.*` imports (alphabetical within groups)

**Example from `src/axon/core/ingestion/pipeline.py`:**
```python
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from axon.config.ignore import load_gitignore
from axon.core.embeddings.embedder import embed_graph
from axon.core.graph.graph import KnowledgeGraph
```

**No path aliases** — all imports use full `axon.*` package paths.

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

**Example — dataclass with defaults (`src/axon/core/ingestion/pipeline.py`):**
```python
@dataclass
class PipelineResult:
    files: int = 0
    symbols: int = 0
    relationships: int = 0
    duration_seconds: float = 0.0
    incremental: bool = False
```

**Example — Protocol interface (`src/axon/core/storage/base.py`):**
```python
@runtime_checkable
class StorageBackend(Protocol):
    def initialize(self, path: Path) -> None: ...
    def add_nodes(self, nodes: list[GraphNode]) -> None: ...
```

## Error Handling Patterns

**CLI layer** (`src/axon/cli/main.py`):
- User-facing errors printed with `console.print("[red]Error:[/red] ...")` then `raise typer.Exit(code=1)`
- Never raises raw exceptions to the user; all error paths are caught and formatted
- `(ValueError, RuntimeError)` caught at the command boundary and re-raised as `typer.Exit`

**Internal layers** (ingestion, storage):
- Errors that must not crash a phase are caught with broad `except Exception` and logged via `logger.warning(..., exc_info=True)` — see embedding phase in `run_pipeline`
- `(json.JSONDecodeError, OSError)` commonly paired for file I/O failure handling
- `(subprocess.TimeoutExpired, FileNotFoundError)` paired for external process calls

**Storage layer:**
- DB errors propagate as `RuntimeError` to the web/CLI layer, which catches them for HTTP 400/500 or typer exit

**Example — controlled failure with logging:**
```python
try:
    _register_in_global_registry(meta, repo_path)
except Exception:
    logger.debug("Failed to register repo in global registry", exc_info=True)
```

**Example — CLI error pattern:**
```python
console.print(f"[red]Error:[/red] {exc}")
raise typer.Exit(code=1) from exc
```

## Comments and Documentation

**Module docstrings:** Every source module has a module-level docstring describing purpose and key contents. Examples: `src/axon/core/ingestion/pipeline.py`, `src/axon/core/parsers/base.py`, `src/axon/core/storage/base.py`.

**Class docstrings:** Dataclasses and protocol classes have short single-line or multi-paragraph docstrings. Field-level comments clarify non-obvious semantics.

**Function docstrings:** Public functions with non-trivial signatures use NumPy-style docstrings with `Parameters`, `Returns` sections — see `run_pipeline` and `reindex_files` in `src/axon/core/ingestion/pipeline.py`.

**Inline comments:** Used sparingly; only where logic is non-obvious. The CONTRIBUTING.md states: "Comments only where the logic isn't self-evident."

**noqa directives:** `# noqa: F821` used for forward-reference string annotations in places where ruff can't resolve the type; `# noqa: S603` used for subprocess calls where the pattern is intentional.

## Module Structure Patterns

**Ingestion phases:** Each pipeline phase lives in its own module under `src/axon/core/ingestion/`. Modules expose a single top-level `process_*` function that takes `(parse_data, graph, ...)` and mutates the graph in place, or returns a list of edges (`collect=True` mode). Example: `src/axon/core/ingestion/calls.py`, `src/axon/core/ingestion/dead_code.py`.

**Parser pattern:** Language parsers subclass `LanguageParser(ABC)` from `src/axon/core/parsers/base.py` and implement `parse(self, content: str, file_path: str) -> ParseResult`. See `src/axon/core/parsers/python_lang.py` and `src/axon/core/parsers/typescript.py`.

**Web routes:** Each domain area has its own `router` in `src/axon/web/routes/`. Routes are thin: they read from `request.app.state.storage` and delegate to business logic functions. No business logic in route handlers.

**Factory functions:** App construction uses factory functions (`create_app` in `src/axon/web/app.py`) rather than global app instances, making tests straightforward.

**Protocol-based abstractions:** `StorageBackend` in `src/axon/core/storage/base.py` is a `Protocol`, not an abstract base class. This allows duck-typed implementations and `MagicMock` usage in tests without subclassing.

## Configuration Approach

**Package config:** `pyproject.toml` is the single configuration file for build, linting, formatting, and test settings. No `setup.py`, `setup.cfg`, or separate config files.

**Runtime config:** No config files loaded at runtime. All runtime parameters passed as function arguments or CLI options. The CLI uses `typer.Option` with defaults for all configurable parameters.

**Ignore patterns:** Language-specific ignore lists in `src/axon/config/ignore.py` and language mappings in `src/axon/config/languages.py`.

**Database path convention:** Index stored at `{repo_root}/.axon/kuzu/`. Metadata at `{repo_root}/.axon/meta.json`. Global registry at `~/.axon/repos/{slug}/meta.json`.

## Design Patterns

**Dataclass-as-DTO:** All inter-layer data transfer uses `@dataclass` instances. No raw dicts passed between modules (except JSON serialization boundaries).

**Enum-based type safety:** `NodeLabel` and `RelType` enums are used throughout instead of raw strings. Mapping dicts (`_LABEL_MAP`, `_REL_TYPE_MAP`) convert between string DB values and enum instances at the storage boundary.

**Deterministic IDs:** Node IDs are generated by `generate_id(label, file_path, symbol_name)` in `src/axon/core/graph/model.py` producing `"{label}:{file_path}:{symbol_name}"`. This enables idempotent bulk-loads (upsert semantics).

**Collect pattern:** Concurrent pipeline phases use `collect=True` to return edge lists instead of mutating the graph directly, allowing thread-safe parallel execution via `ThreadPoolExecutor`.

---

*Convention analysis: 2026-03-23*
