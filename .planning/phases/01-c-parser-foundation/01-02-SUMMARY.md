---
phase: 01-c-parser-foundation
plan: 02
subsystem: parser
tags: [tree-sitter, csharp, parser, tdd, symbol-extraction, heritage, import-resolution]

# Dependency graph
requires:
  - 01-01 (tree-sitter-c-sharp installed, SymbolInfo.properties field, .cs extension registered)
provides:
  - CSharpParser implementing LanguageParser in src/axon/core/parsers/csharp_lang.py
  - resolve_csharp_imports() post-processor for namespace-to-file resolution
  - All 21 test_parser_csharp.py tests passing (6 classes green)
affects: [01-03, 02-01, 03-01]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Block-style namespace (namespace_declaration) uses child_by_field_name('body'); file-scoped namespace pre-scanned in parse() to set self._current_namespace"
    - "Heritage via base_list iteration (not child_by_field_name — base_list is NOT a named field); I-prefix heuristic distinguishes implements from extends"
    - "properties dict pattern: cs_namespace always stored if non-empty; cs_attributes stored on every class/interface/method node"
    - "resolve_csharp_imports uses duck-typed list parameter (not FileParseData annotation) to avoid circular import with parser_phase.py"

key-files:
  created:
    - src/axon/core/parsers/csharp_lang.py

key-decisions:
  - "Property nodes use kind='method' per D-04 (one node per property, no per-accessor nodes)"
  - "Struct declarations handled identically to class declarations — emitted as kind='class' nodes"
  - "Nested classes extracted as first-class nodes with class_name='outer_class' set by the parent walk"
  - "File-scoped namespace (C# 10+ semicolon form) handled by pre-scan in parse() before main walk"
  - "resolve_csharp_imports uses list (not list[FileParseData]) to avoid circular import"

# Metrics
duration: 10min
completed: 2026-03-23
---

# Phase 1 Plan 02: CSharpParser Implementation Summary

**CSharpParser implemented with full symbol extraction, heritage, attributes, namespace tracking, using directive extraction, and resolve_csharp_imports — all 21 test_parser_csharp.py tests green**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-23T20:44:10Z
- **Completed:** 2026-03-23T20:54:10Z
- **Tasks:** 2
- **Files created:** 1 (csharp_lang.py, 500 lines)

## Accomplishments

Created `src/axon/core/parsers/csharp_lang.py` with the complete `CSharpParser` implementation:

**Methods implemented:**

- `__init__()` — Parser(CS_LANGUAGE) initialization with `self._current_namespace` instance state
- `parse()` — entry point with file-scoped namespace pre-scan + compilation_unit walk
- `_walk()` — dispatches to extraction methods via match statement on node.type
- `_extract_namespace()` — block-style namespace extraction with save/restore of `_current_namespace`
- `_get_namespace_name()` — extracts qualified_name or identifier text from namespace node
- `_extract_class()` — class/struct declaration with partial modifier detection, attributes, namespace, heritage, body walk
- `_extract_interface()` — interface declaration with attributes, namespace, heritage, body walk
- `_extract_method()` — method declaration with signature building and param type refs
- `_extract_constructor()` — constructor as kind="method" node
- `_extract_property()` — property declaration as kind="method" node per D-04
- `_extract_enum()` — enum declaration with namespace property
- `_extract_using()` — all three using forms (plain, static, alias) with Pitfall 5 alias handling
- `_extract_heritage()` — base_list iteration with I-prefix heuristic
- `_extract_attributes()` — attribute_list unnamed children iteration
- `_build_method_signature()` — `"return_type method_name(params)"` format
- `_extract_param_type_refs()` — parameter type annotation extraction for non-builtin types

**Module-level function:**

- `resolve_csharp_imports(all_parse_data: list) -> None` — second-pass namespace-to-file resolver

## Task Commits

1. **Tasks 1 + 2: Full CSharpParser implementation** — `93ef1b9` (feat)
   - Both tasks committed as one atomic change since they produce the same file

## Test Results

All 21 tests in `tests/core/test_parser_csharp.py` pass:

| Class | Tests | Status |
|-------|-------|--------|
| TestRegistration | 3 | PASS |
| TestImport | 2 | PASS |
| TestSymbolExtraction | 5 | PASS |
| TestImportResolution | 4 | PASS |
| TestHeritage | 3 | PASS |
| TestProperties | 4 | PASS |
| **Total** | **21** | **PASS** |

Existing test suite: 101 parser + dead-code tests unaffected (all pass).

## Open Question Resolutions

1. **Nested class extraction**: Nested classes are extracted as first-class nodes — walker passes `class_name=outer_class_name` so nested members get the outer class as context; the nested class itself has no `class_name` set on its SymbolInfo (consistent with Python parser behavior).

2. **struct_declaration handling**: Structs are emitted as `kind="class"` nodes — value-type analogs of classes, simplest correct behavior per open question recommendation.

3. **Constructor naming**: Constructors extracted as Method nodes with `name = constructor_name` (same as the class name for C# constructors) — appears in call graphs correctly.

## Deviations from Plan

### Auto-resolved implementation detail

**[Discretion - File-scoped namespace walk] Pre-scan approach for file-scoped namespaces**

The plan described two approaches for file-scoped namespaces. The pre-scan approach (scan children first for `file_scoped_namespace_declaration`, set `_current_namespace`, then walk) was implemented instead of recursing into a non-existent body node. The `_walk` match statement treats `file_scoped_namespace_declaration` as a no-op (pre-scan already handled it). This correctly handles all C# 10+ file-scoped namespace code.

No other deviations — all RESEARCH.md patterns used verbatim.

## Known Stubs

None — all data flows are wired. The `resolve_csharp_imports` function is complete and functional; it is wired into `parser_phase.py` in Plan 03.

## Self-Check: PASSED

- FOUND: `src/axon/core/parsers/csharp_lang.py` (500 lines)
- FOUND: `.planning/phases/01-c-parser-foundation/01-02-SUMMARY.md`
- FOUND: commit `93ef1b9` (feat(01-02): implement CSharpParser)
- All 21 tests in `test_parser_csharp.py` confirmed passing
- Existing test suite unaffected (101 parser + dead-code tests pass)

---
*Phase: 01-c-parser-foundation*
*Completed: 2026-03-23*
