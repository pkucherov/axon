---
phase: 01-c-parser-foundation
plan: 03
subsystem: parsing
tags: [csharp, tree-sitter, parser-phase, pipeline-integration, collision-detection]

# Dependency graph
requires:
  - phase: 01-02
    provides: CSharpParser class and resolve_csharp_imports function in csharp_lang.py
provides:
  - CSharpParser registered in _PARSER_FACTORIES under 'csharp' key
  - _qualify_collisions post-parse hook in parser_phase.py (D-05/D-06)
  - resolve_csharp_imports called after parallel parse loop (D-01/D-03)
  - get_parser('csharp') returns CSharpParser without ValueError
  - Full end-to-end C# indexing via axon analyze
affects:
  - phase 02 (UE5 C++ will follow same registration pattern)
  - phase 03 (AngelScript follows same pattern)
  - phase 05 (Unity lifecycle exemptions build on this pipeline wiring)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Post-parse hooks pattern: call language-specific post-processors after ThreadPoolExecutor, before graph node creation"
    - "Collision detection: second-pass scan over all_parse_data before graph writes to qualify ambiguous names"

key-files:
  created: []
  modified:
    - src/axon/core/ingestion/parser_phase.py
    - src/axon/core/parsers/csharp_lang.py
    - src/axon/core/parsers/base.py
    - tests/core/test_parser_csharp.py

key-decisions:
  - "Post-parse hooks call site: after ThreadPoolExecutor block, before sequential for loop — ensures all namespace data available before graph nodes created"
  - "Hook order: _qualify_collisions before resolve_csharp_imports — both operate on symbol names before graph writes"
  - "_qualify_collisions placed as module-level helper, not inside process_parsing — consistent with existing module structure"

patterns-established:
  - "Phase registration pattern: import Parser + resolver, add to _PARSER_FACTORIES, update error message, add post-parse hooks"
  - "Post-parse hooks are language-specific cleanup functions that mutate parse results before graph creation"

requirements-completed: [INFRA-01, CS-02]

# Metrics
duration: 25min
completed: 2026-03-23
---

# Phase 01 Plan 03: C# Parser Pipeline Integration Summary

**CSharpParser wired into ingestion pipeline with namespace collision detection and import resolution — .cs files now fully indexed via `axon analyze`**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-23T21:00:00Z
- **Completed:** 2026-03-23T21:25:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Registered `CSharpParser` in `_PARSER_FACTORIES` — `get_parser('csharp')` returns a `CSharpParser` instance
- Added `_qualify_collisions` module-level function to `parser_phase.py` for D-05/D-06 collision detection
- Added two post-parse hook calls in `process_parsing` after parallel parse, before graph node creation
- Ruff lint passes on all modified files (removed unused import, shortened two over-100-char lines)
- 698 core tests collected; all new 8 pipeline integration tests pass; all 21 original C# tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Pipeline integration tests** - `c45176e` (test)
2. **Task 1 (GREEN): Register CSharpParser and add hooks** - `0d6c112` (feat)
3. **Task 2: Ruff lint fixes** - `77b9c49` (fix)

_Note: TDD task had two commits — RED (failing tests) then GREEN (implementation)_

## Files Created/Modified

- `src/axon/core/ingestion/parser_phase.py` — Added CSharpParser import, registration, `_qualify_collisions` function, post-parse hook calls
- `src/axon/core/parsers/csharp_lang.py` — Removed unused `CallInfo` import; shortened docstring line
- `src/axon/core/parsers/base.py` — Shortened `decorators` field comment to fit 100-char limit
- `tests/core/test_parser_csharp.py` — Added `TestPipelineRegistration` (3 tests) and `TestQualifyCollisions` (5 tests)

## Decisions Made

- Post-parse hook placement confirmed at the exact boundary specified in the plan: after `list(executor.map(...))` and before `for file_entry, parse_data in zip(...)`. This ordering is required — collision detection must run before `symbol.name` is consumed by `graph.add_node`, and import resolution must run before the imports phase creates IMPORTS edges.
- `_qualify_collisions` defined as a module-level function (not nested inside `process_parsing`) for testability and consistency with the existing module style.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff violations in pre-existing and new code**
- **Found during:** Task 2 (ruff lint pass)
- **Issue:** Three violations: unused `CallInfo` import in csharp_lang.py (F401), two over-100-char lines (E501) — one in base.py `decorators` comment, one in csharp_lang.py `_extract_using` docstring
- **Fix:** Removed `CallInfo` from imports; shortened both comments to fit within 100-char limit
- **Files modified:** `src/axon/core/parsers/csharp_lang.py`, `src/axon/core/parsers/base.py`
- **Verification:** `ruff check` exits 0 with "All checks passed!"
- **Committed in:** `77b9c49` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - lint violations in new/existing code)
**Impact on plan:** Required for ruff CI compliance. No scope creep.

## Issues Encountered

None — plan executed cleanly once ruff violations were fixed.

## Phase 1 Requirements Coverage

All 6 Phase 1 requirements have green test coverage:

| Requirement | Description | Status | Test Coverage |
|---|---|---|---|
| INFRA-01 | .cs extension maps to 'csharp' language key | COMPLETE | `TestRegistration` (3 tests) |
| INFRA-05 | tree-sitter-c-sharp importable; CSharpParser instantiates | COMPLETE | `TestImport` (2 tests) |
| CS-01 | Class, method, interface, namespace extraction | COMPLETE | `TestSymbolExtraction` (5 tests) |
| CS-02 | using directive extraction + namespace→file resolution | COMPLETE | `TestImportResolution` (4 tests) + `TestPipelineRegistration` |
| CS-03 | Heritage (extends/implements) edges via I-prefix heuristic | COMPLETE | `TestHeritage` (3 tests) |
| CS-04 | Properties as Method nodes with owning class_name | COMPLETE | `TestProperties` (4 tests) |

## Final Test Count

- **Total C# tests:** 29 (21 original + 8 new pipeline integration tests)
- **Core tests collected:** 698 (original 669 + 21 CS-01–CS-04 + 8 pipeline integration)
- **Failures:** 0

## End-to-End Smoke Test Results

All three smoke tests from the plan's verification section pass:
1. `get_language('Foo.cs')` → `"csharp"` ✓
2. `CSharpParser().parse(...)` → `[('Foo', 'class', ''), ('Bar', 'method', 'Foo')]` ✓
3. `get_parser('csharp')` → `CSharpParser` ✓

## Observations for Phase 2 (UE5 C++)

The post-parse hooks pattern established here (two hook calls after parallel parse, before sequential graph loop) will be reused for UE5 C++:
- UE5 will need a `resolve_ue5_module_imports` hook (similar to `resolve_csharp_imports`)
- Collision detection may not be needed for C++ (namespaces in tree-sitter typically produce unique qualified names)
- Registration pattern: import `UE5Parser`, add `"cpp_ue5": UE5Parser` to `_PARSER_FACTORIES`, update error message

## Next Phase Readiness

Phase 01 (C# Parser Foundation) is **complete**. All requirements INFRA-01, INFRA-05, CS-01–CS-04 have passing test coverage. Phase 02 (AngelScript binding spike) and Phase 03 (UE5 C++ parser) can proceed independently — no blockers.

---
*Phase: 01-c-parser-foundation*
*Completed: 2026-03-23*
