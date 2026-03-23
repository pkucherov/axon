# Axon — Language Extension: C#, UE5 C++, AngelScript

## What This Is

Axon is a code intelligence engine that ingests source repositories into an embedded graph database (KuzuDB) and exposes the resulting knowledge graph through a CLI, MCP server (15 AI tools), and a React web UI. It currently supports Python, TypeScript, TSX, and JavaScript via tree-sitter parsers. This milestone adds three new language parsers — C#, Unreal Engine 5 C++, and UnrealAngel AngelScript — with full UE5-awareness built in from the start.

## Core Value

AI agents and developers can navigate, search, and understand Unreal Engine 5 codebases the same way they can Python and TypeScript ones — with correct UE5 macro semantics, module boundaries, and Blueprint exposure surfaced in the graph.

## Requirements

### Validated

- ✓ Python parsing via tree-sitter — functions, classes, methods, imports, calls — existing
- ✓ TypeScript/TSX/JavaScript parsing — same symbol types plus exports/heritage — existing
- ✓ 11-phase ingestion pipeline (structure → parse → imports → calls → heritage → types → community → processes → dead code → coupling) — existing
- ✓ KuzuDB graph persistence with BM25 FTS + vector hybrid search — existing
- ✓ MCP server with 15 tools exposed to AI agents (stdio + HTTP) — existing
- ✓ React web UI with force-directed graph visualization — existing
- ✓ Dead code detection (is_dead flag, entry-point awareness, constructor/dunder/test exemptions) — existing
- ✓ Community detection via Leiden clustering — existing
- ✓ Git co-change coupling analysis — existing
- ✓ Incremental re-indexing via file watcher — existing

### Active

- [ ] C# parser: extract functions, methods, classes, interfaces, properties from .cs files (tree-sitter-c-sharp)
- [ ] C# Unity-awareness: detect MonoBehaviour subclasses, [SerializeField]/[Header]/[RequireComponent] attributes as node metadata; Unity lifecycle methods (Start, Update, Awake, etc.) exempt from dead-code
- [ ] C# general .NET support: works on non-Unity codebases without Unity-specific assumptions
- [ ] UE5 C++ parser: extract functions, methods, classes from .h/.cpp files (tree-sitter-cpp)
- [ ] UE5 macro awareness: UCLASS/USTRUCT/UENUM/UFUNCTION/UPROPERTY parsed and stored as node metadata properties (not separate nodes)
- [ ] UE5 Blueprint exposure: BlueprintCallable, BlueprintEvent, BlueprintNativeEvent flags surfaced as metadata; these nodes exempt from dead-code detection
- [ ] UE5 base class registry: AActor, UObject, UActorComponent, ACharacter, AGameMode, UWidget, etc. treated as known external types — not flagged as unknown or dead
- [ ] UE5 Module nodes: .Build.cs files parsed to extract module name and dependencies; emit MODULE nodes with DEPENDS_ON edges between modules
- [ ] AngelScript parser: extract functions, methods, classes from .as files (UnrealAngel / Hazelight dialect)
- [ ] AngelScript UE5 integration awareness: UCLASS/UFUNCTION equivalents in AS syntax; mixin classes; UE-style inheritance
- [ ] Inheritance edges for all three languages: EXTENDS/IMPLEMENTS relationships fed into dead-code and heritage phases
- [ ] Dead-code exemptions updated: UE5 Blueprint-exposed functions, Unity lifecycle methods, and AngelScript UE-annotated functions are never flagged dead
- [ ] All three languages registered in languages.py and parser_phase.py with correct file extension mappings (.cs, .h, .cpp, .as, .Build.cs)

### Out of Scope

- Full UE5 reflection system deep-dive (UHT-generated headers, .generated.h files) — too complex for v1; store as opaque metadata
- C++/CLI or mixed-mode C++ (non-UE5 C++) — v1 targets UE5 specifically
- Roslyn-level C# semantic analysis — tree-sitter structural parsing is sufficient for the graph
- Blueprint visual scripting graphs (.uasset parsing) — binary format, not practical for tree-sitter
- Game-specific runtime analysis (profiling, memory) — out of scope for static graph analysis

## Context

Axon's parser extension point is clean: implement `LanguageParser` protocol in `src/axon/core/parsers/`, register in `parser_phase.py:_PARSER_FACTORIES`, add extension mapping in `languages.py`. The existing dead-code exemption system already has hooks for entry points, constructors, dunders, test functions, decorators, and protocol conformance — it needs to be extended for UE5 Blueprint exposure and Unity lifecycle methods.

Tree-sitter grammars exist for C# (`tree-sitter-c-sharp`) and C++ (`tree-sitter-cpp`). AngelScript may require `tree-sitter-angelscript` (community grammar) or a custom fallback parser. The Module node type (`NodeLabel.MODULE`) does not yet exist and will need to be added to `model.py` with corresponding KuzuDB schema support.

A real UE5/AngelScript repository is available for validation throughout development.

## Constraints

- **Tech stack**: tree-sitter for parsing — consistent with existing Python/TS parsers; new grammars added as pyproject.toml dependencies
- **Parser protocol**: new parsers must implement `LanguageParser` from `base.py` — `ParseResult` dataclass drives all downstream phases unchanged
- **Graph model**: new node/relationship types go in `model.py` enums; KuzuDB schema creation is automatic from the enum
- **Compatibility**: existing Python/TS indexing must be unaffected; dead-code logic changes must not regress existing exemption tests (818 tests currently passing)
- **No new infrastructure**: no additional databases, services, or runtimes introduced

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| tree-sitter for C# and C++ | Consistent with existing parser system; grammars available on PyPI | — Pending |
| UCLASS/UFUNCTION as node metadata (not graph nodes) | Keeps graph model simple; reflection data queryable via node properties | — Pending |
| MODULE as a new NodeLabel | Modules are architectural units with real dependency edges; worth first-class status | — Pending |
| UE5 base class registry in dead_code.py | Avoids false positives without requiring full type resolution | — Pending |
| AngelScript grammar strategy | Community grammar vs custom parser — decide after research | — Pending |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-23 after initialization*
