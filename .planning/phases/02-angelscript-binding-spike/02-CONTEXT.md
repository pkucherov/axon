# Phase 2: AngelScript Binding Spike - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Research and produce a working Python-importable binding for an AngelScript tree-sitter grammar. Evaluate `Relrin/tree-sitter-angelscript` and `dimitrijejankov/tree-sitter-unreal-angelscript`; use the Hazelight PEGGY parser as the authoritative reference for UnrealAngel syntax. Vendor the chosen grammar in `third-party/`, build a proper Python wheel, and install it as a local path dependency. Validate the grammar against full UnrealAngel coverage criteria. If coverage is insufficient, extend the grammar using Hazelight as the spec. Deliver a committed, importable binding and a spike test that proves it works. AngelScript parser implementation is Phase 4 — this phase only establishes the binding.

</domain>

<decisions>
## Implementation Decisions

### Grammar Source
- **D-01:** Evaluate both `Relrin/tree-sitter-angelscript` and `dimitrijejankov/tree-sitter-unreal-angelscript` during the spike. Test both against sample UnrealAngel AngelScript files. Pick the grammar with better UE5/UnrealAngel construct coverage.
- **D-02:** Use the Hazelight VS Code extension (`Hazelight/vscode-unreal-angelscript`) as the authoritative reference for UnrealAngel AngelScript syntax. The Hazelight parser uses PEGGY (PEG.js successor) — extract grammar.js from it as the source of truth when evaluating coverage gaps and when extending the chosen grammar.
- **D-03:** If the better grammar has gaps after evaluation, fork it into `third-party/` and extend `grammar.js` using the Hazelight PEGGY grammar as the reference spec. Do not fall back to a regex-based parser — prefer extending the tree-sitter grammar.

### Binding Mechanism
- **D-04:** Build a proper Python wheel from the vendored grammar source. The wheel must expose a `.language()` function that returns a `PyCapsule`, matching the exact import pattern used by existing parsers:
  ```python
  import tree_sitter_angelscript as tsas
  AS_LANGUAGE = Language(tsas.language())
  ```
  This is consistent with `tree_sitter_c_sharp`, `tree_sitter_cpp`, etc. and is the cleanest long-term approach.

### Distribution
- **D-05:** Vendor the chosen grammar under `third-party/tree-sitter-angelscript/` at the repo root (conventional third-party source path).
- **D-06:** Add a local path dependency to `pyproject.toml`:
  ```
  "tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript"
  ```
  Running `uv sync` builds and installs the package automatically — zero manual steps.

### Spike Success Criteria (Phase 4 green-light)
- **D-07:** Full UnrealAngel coverage required. The spike test must prove the grammar can parse all of the following from `.as` sample files:
  1. Function declarations (standalone and method)
  2. Class declarations with inheritance (`:` syntax, parent class name)
  3. UE5-style annotations — `UCLASS(...)`, mixin class markers, `UFUNCTION(...)`-equivalent decorators
  4. `#include` / import directives
  If any of these four fail, the grammar must be extended (D-03) before Phase 4 can begin.

### Phase 4 Dependency Lock
- **D-08:** Phase 4 (AngelScript Parser Implementation) is blocked on this spike completing with a committed, importable binding. The `03-CONTEXT.md` for Phase 4 must reference the spike output from `third-party/tree-sitter-angelscript/` and the coverage notes produced here.

### Claude's Discretion
- Which grammar (Relrin vs dimitrijejankov) is ultimately selected — determined by spike evaluation results
- Exact Python package name used in pyproject.toml (may be `tree-sitter-angelscript`, `tree-sitter-unreal-angelscript`, or a renamed fork)
- Grammar extension scope — which specific grammar rules need to be added or patched to meet D-07
- Test sample file content for the spike validation tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Grammar Repos (evaluate both)
- `https://github.com/Relrin/tree-sitter-angelscript` — Generic AngelScript tree-sitter grammar (external; clone/fork into third-party/)
- `https://github.com/dimitrijejankov/tree-sitter-unreal-angelscript` — UE5-specific UnrealAngel tree-sitter grammar (external; clone/fork into third-party/)

### Authoritative Syntax Reference
- `https://github.com/Hazelight/vscode-unreal-angelscript` — Hazelight VS Code extension using a PEGGY parser; `grammar.js` (or equivalent parser source) is the authoritative UnrealAngel syntax spec. Researcher must locate the parser entry point in this repo and extract the grammar rules.

### Parser Protocol
- `src/axon/core/parsers/base.py` — `LanguageParser` ABC, `ParseResult`, `SymbolInfo` — the protocol Phase 4 will implement
- `src/axon/core/parsers/csharp_lang.py` — Reference for how to load a tree-sitter language and implement the parser pattern
- `src/axon/core/parsers/python_lang.py` — Second reference parser with recursive walk pattern

### Build/Packaging
- `pyproject.toml` — Where the path dependency will be added; see existing `tree-sitter-c-sharp` entry for the pattern
- `uv.lock` — Lockfile that will be updated when the path dep is added

### Requirements
- `.planning/REQUIREMENTS.md` §INFRA-06 — Exact acceptance criteria for Phase 2

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Language(tscsharp.language())` pattern in `csharp_lang.py:27` — the exact API the AngelScript binding must match
- `pyproject.toml` lines 30–31 — `tree-sitter-c-sharp` and `tree-sitter-cpp` entries as the model for adding the path dependency
- `src/axon/core/parsers/base.py` — `LanguageParser`, `ParseResult`, `SymbolInfo` — Phase 4 will consume these; spike test can import them to prototype extraction

### Established Patterns
- All parsers: `Language(pkg.language())` at module level, `Parser(LANGUAGE)` in `__init__`, stateless `_walk()` — the binding must expose `.language()` capsule
- `tree-sitter >= 0.25.0` is pinned — `Language.build_library()` is gone; wheel-based approach is required
- No `[extras]` that pin older tree-sitter versions (locked in Phase 1 D-07)

### Integration Points
- `src/axon/config/languages.py::SUPPORTED_EXTENSIONS` — will need `".as": "angelscript"` in Phase 4 (not Phase 2)
- `src/axon/core/ingestion/parser_phase.py::_PARSER_FACTORIES` — will need AngelScript entry in Phase 4 (not Phase 2)
- `third-party/` directory at repo root — does not yet exist; this phase creates it

</code_context>

<specifics>
## Specific Ideas

- Hazelight PEGGY grammar is the authoritative spec: extract `grammar.js` (or parser source) from `Hazelight/vscode-unreal-angelscript` and use it to verify coverage and guide grammar extensions
- The dimitrijejankov grammar may already be a better match for UnrealAngel — evaluate it first since it's UE5-specific
- The spike deliverable is not just a decision document — it must produce a committed, importable Python package that Phase 4 can use directly

</specifics>

<deferred>
## Deferred Ideas

- AngelScript parser implementation (functions, methods, IMPORTS edges) — Phase 4
- Registering `.as` in `languages.py` and `_PARSER_FACTORIES` — Phase 4
- UE5 annotations extraction logic for AngelScript — Phase 4 (grammar just needs to expose the node types; extraction logic is Phase 4 work)
- Publishing the AngelScript wheel to PyPI — post-v1 if needed

</deferred>

---

*Phase: 02-angelscript-binding-spike*
*Context gathered: 2026-03-27*
