---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
stopped_at: Phase 02 context gathered
last_updated: "2026-03-27T12:49:31.978Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 4
  completed_plans: 4
---

# State — Axon Language Extension: C#, UE5 C++, AngelScript

**Milestone:** v1 Language Support
**Created:** 2026-03-23
**Last Updated:** 2026-03-23T20:42Z

---

## Project Reference

**Core Value:** AI agents and developers can navigate, search, and understand Unreal Engine 5 and Unity codebases with correct UE5 macro semantics, module boundaries, Blueprint exposure, and lifecycle method awareness surfaced in the code intelligence graph.

**Current Focus:** Phase 01 — c-parser-foundation

**Constraints:**

- Tech stack: tree-sitter parsers (consistent with existing Python/TypeScript)
- Parser protocol: must implement LanguageParser and emit ParseResult dataclass
- Graph model: new node/relationship types in model.py; KuzuDB schema automatic
- Compatibility: existing Python/TS indexing must remain unaffected
- No new infrastructure: embedded KuzuDB only, no external services

---

## Current Position

Phase: 2
Plan: Not started

## Performance Metrics

**Test Coverage Target:** 90% on core modules (inherited from existing baseline of 818 tests, 3505 stmts)

**Expected new test files:**

- `tests/core/test_parser_csharp.py` — 80+ tests for C# parser
- `tests/core/test_parser_cpp_ue5.py` — 100+ tests for UE5 C++ parser (macro extraction focus)
- `tests/core/test_parser_angelscript.py` — 80+ tests for AngelScript parser
- Extended `tests/core/test_dead_code.py` — Blueprint/lifecycle exemptions
- Extended `tests/core/test_ue5_utils.py` — UE5 macro patterns, base class registry

**Estimated new lines of test code:** 300+ tests, ~3000 lines

**Coverage by module (post-completion):**

- `csharp_parser.py`: Target 90%
- `cpp_ue5_parser.py`: Target 90%
- `angelscript_parser.py`: Target 90%
- `ue5_utils.py`: Target 95%
- `dead_code.py`: Extended to 92% (macros + lifecycle)

---

## Accumulated Context

### Key Decisions Locked

1. **Parser build order:** C# → UE5 C++ → AngelScript
   - C# has no macro preprocessing; establishes baseline pattern
   - UE5 C++ depends on C# pattern; enables ue5_utils.py for Phase 3
   - AngelScript reuses C++ patterns; highest risk (grammar uncertainty)

2. **UE5 metadata storage:** Properties dict, not separate graph nodes
   - UCLASS/UFUNCTION/UPROPERTY stored in `node.properties["ue_specifiers"]`
   - Keeps graph model simple; avoids bloat; queryable via JSON fields
   - Dead-code exemptions check properties dict only

3. **Exemption logic:** Centralized in dead_code.py + ue5_utils.py
   - Parsers extract facts (decorators, attributes, macros)
   - Exemption checks are pure functions; no language-specific coupling
   - All changes to exemption logic require test validation

4. **AngelScript binding strategy:** Custom Python binding (2-3 weeks) vs regex fallback
   - Phase 2 spike validates Relrin/tree-sitter-angelscript grammar
   - If grammar insufficient, fallback to regex-based parser (lower confidence but faster)
   - Decision locked by end of Phase 2

5. **Module nodes deferral:** Phase 6, separable from parsing
   - .Build.cs parsing can wait until core three languages work
   - MODULE node type added late in milestone (low risk if deferred to v2)
   - Enables v1 to ship without architectural components

6. **tree-sitter-c-sharp dependency: base package only** (locked in Plan 01-01)
   - Do NOT use `tree-sitter-c-sharp[core]` extra — it pins `tree-sitter~=0.22` conflicting with `tree-sitter>=0.25.0`
   - Use `"tree-sitter-c-sharp>=0.23.0"` without extras

7. **SymbolInfo.properties pattern established** (locked in Plan 01-01)
   - `properties: dict = field(default_factory=dict)` — keyword field, fully backward-compatible
   - All language parsers store metadata (cs_namespace, cs_attributes, ue_specifiers) via this field
   - `parser_phase.py` merges `symbol.properties` into `GraphNode.properties` generically

8. **C# property nodes use kind='method'** (locked in Plan 01-02, per D-04)
   - One Method node per property declaration; no per-accessor nodes
   - All property forms (auto, read-only, expression-bodied) follow the same pattern
   - class_name set to the owning class

9. **resolve_csharp_imports uses duck-typed list parameter** (locked in Plan 01-02)
   - `all_parse_data: list` (not `list[FileParseData]`) to avoid circular import with parser_phase.py
   - Operates on objects with .language, .file_path, .parse_result attributes

10. **Post-parse hook pattern established** (locked in Plan 01-03)
    - Hook calls placed after `ThreadPoolExecutor` block, before `for file_entry, parse_data in zip(...)` loop
    - This ordering ensures all namespace data is available before graph nodes are created
    - Future languages (UE5 C++, AngelScript) follow the same registration + post-parse hook pattern

### Research Risks (Tracked)

**High Priority:**

- **Phase 2:** AngelScript grammar availability and Python binding feasibility — spike validates
- **Phase 3:** UE5 macro extraction edge cases (multiline, nested parentheses) — regex tested on real headers
- **Phase 3:** .Build.cs file structure confirmation — validate module dependencies exist

**Medium Priority:**

- **Phase 5:** C# partial class merging semantics — test on real Unity projects
- **Phase 5:** Unity lifecycle method list completeness — cross-check against official docs
- **Phase 6:** Cross-language import resolution coherence — spot-check on multi-language projects

### Probable Blockers

1. **AngelScript grammar not available/unmaintained** → Fallback to regex parser (Phase 2 spike mitigates)
2. **UE5 macro extraction fragile on edge cases** → Comprehensive regex tests + real-world validation (Phase 3 includes spike)
3. **Import resolution missing across languages** → Phase 5 includes spot-check validation
4. **Partial class handling in C#** → Document limitations in Phase 1; defer deeper semantic merging to v2

### Work in Progress

None — Phase 01 complete. Next: Phase 02 planning (AngelScript binding spike).

### Completed Work

- [x] Research completed (SUMMARY.md validated)
- [x] Requirements extracted and categorized (29 total)
- [x] Roadmap created with 6 phases
- [x] Success criteria derived for all phases
- [x] 100% requirement coverage validated
- [x] Plan 01-01: Infrastructure foundation — tree-sitter-c-sharp/cpp installed, .cs registered, SymbolInfo.properties added, Wave 0 test scaffold created (commits 3255c18, d33f70b)
- [x] Plan 01-02: CSharpParser implementation — all 21 tests green; CS-01, CS-02, CS-03, CS-04 complete (commit 93ef1b9)
- [x] Plan 01-03: C# parser pipeline integration — CSharpParser registered in _PARSER_FACTORIES; _qualify_collisions and resolve_csharp_imports called in process_parsing; 29/29 C# tests green; ruff passes (commits c45176e, 0d6c112, 77b9c49)

### Pending

- [ ] Phase 2 planning (AngelScript binding spike)
- [ ] Phase 3 planning (UE5 C++ parser + macro extraction)
- [ ] Phases 4–6 planning

---

## Session Continuity

**Last session focus:** Plan 01-03 executed — CSharpParser wired into pipeline; 29/29 C# tests green; ruff clean
**Stopped at:** Phase 02 context gathered
**Next session focus:** Phase 02 planning — AngelScript binding spike (evaluate tree-sitter-angelscript grammar)
**Context preserved in:** ROADMAP.md (structure), STATE.md (decisions), REQUIREMENTS.md (traceability), 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md

**For future sessions:**

- Phases 1–3 are critical path; parallel execution of Phase 2 recommended
- Phase 3 macro extraction is highest fragility point; spike validation required
- Phase 5 exemptions depend on Phases 1 and 3 being complete
- Phase 6 is optional end-of-milestone; can defer to v2 if time constrained

---

*Last updated: 2026-03-23 (initial creation)*
