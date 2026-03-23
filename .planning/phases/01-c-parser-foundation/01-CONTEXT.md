# Phase 1: C# Parser Foundation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement a tree-sitter-based C# parser that extracts functions, methods, classes, interfaces, and properties from .cs files. Register the parser in the existing parser pipeline. Establish the parser pattern (file structure, SymbolInfo extension) that Phases 3 and 4 will follow. Unity lifecycle exemptions and partial class merging are Phase 5 concerns — not in scope here.

</domain>

<decisions>
## Implementation Decisions

### Import Resolution
- **D-01:** Best-effort namespace-to-file resolution. `using` directives are resolved by scanning indexed .cs files for matching `namespace X.Y.Z` declarations, then emitting IMPORTS edges to those files. Unresolved namespaces silently produce no edges.
- **D-02:** All three `using` forms are extracted with the same strategy: plain `using Namespace;`, `using static Type;`, and `using Alias = Type;`. Resolution treats each the same way — map to the file declaring the referenced namespace/type.
- **D-03:** Resolution logic lives in the C# parser module (`csharp_lang.py`), not mixed into `imports.py`. The logic runs after all files are parsed so namespace→file mapping is complete.

### Property Node Representation
- **D-04:** One Method node per property, named by the property name (e.g., `MyProperty`). Kind = `"method"`, `class_name` = owning class. Read-only, write-only, and expression-bodied properties all follow the same pattern. No per-accessor nodes.

### Namespace Qualification
- **D-05:** Simple names by default (e.g., `MyActor`, not `Unreal.Core.MyActor`) — consistent with the Python/TS parsers. Only qualify on name collision: if two classes in the same project share the same simple name, both get the fully qualified name.
- **D-06:** Collision detection runs in `parser_phase.py` as a post-parse second pass over all parsed C# files before graph nodes are created. The namespace is always stored in `properties["cs_namespace"]` regardless of whether qualification was applied.

### SymbolInfo Extension
- **D-07:** Add `properties: dict = field(default_factory=dict)` to `SymbolInfo` in `base.py` during Phase 1. This is needed by Phase 3 (UE5 specifiers) and used in Phase 1 for C# attributes. All existing parsers are unaffected (field has a default).
- **D-08:** C# class/method attributes (e.g., `[Serializable]`, `[DllImport("...")]`, `[Obsolete]`) are extracted in Phase 1 and stored as a list in `properties["cs_attributes"]`. Phase 3 will use `properties["ue_specifiers"]` using the same dict pattern.

### Partial Classes
- **D-09:** Phase 1 emits one Class node per file for partial classes — duplicates exist in the graph. This is the accepted baseline behavior. Phase 5 merges them. The known limitation is documented in the parser's module docstring.

### Claude's Discretion
- Exact tree-sitter node type names for the C# grammar (discovered during implementation)
- Content of the `_BUILTIN_TYPES` frozenset for C#
- Whether nested types (classes inside classes) are extracted or skipped in Phase 1
- Signature string format for C# methods

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Parser Protocol
- `src/axon/core/parsers/base.py` — `LanguageParser` ABC, `ParseResult`, `SymbolInfo`, `ImportInfo`, `CallInfo`, `TypeRef` — the exact protocol the C# parser must implement; `properties: dict` field to be added here
- `src/axon/core/parsers/python_lang.py` — canonical reference parser: recursive AST walk, `_extract_function`, `_extract_class`, `_extract_import` patterns
- `src/axon/core/parsers/typescript.py` — second reference parser: dialect dispatch, `_walk` with visited set, heritage extraction

### Registration Points
- `src/axon/config/languages.py` — `SUPPORTED_EXTENSIONS` dict; add `".cs": "csharp"`
- `src/axon/core/ingestion/parser_phase.py` — `_PARSER_FACTORIES` dict; add `"csharp": CSharpParser`; `_KIND_TO_LABEL` for symbol kind dispatch

### Requirements
- `.planning/REQUIREMENTS.md` §INFRA-01, §INFRA-05, §CS-01 through §CS-04 — exact acceptance criteria for Phase 1

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LanguageParser(ABC)` in `base.py`: single `parse(content: str, file_path: str) -> ParseResult` method — C# parser implements this directly
- `ParseResult` dataclass: `symbols`, `imports`, `calls`, `type_refs`, `heritage`, `exports` fields — all relevant for C#
- `SymbolInfo.decorators: list[str]` — already exists; C# attributes go into `properties["cs_attributes"]` (new dict field), not `decorators`

### Established Patterns
- Both existing parsers use `Parser(LANGUAGE)` from tree-sitter, parse bytes, then do a recursive `_walk()` on `tree.root_node`
- `_KIND_TO_LABEL` in `parser_phase.py` dispatches `kind` strings to `NodeLabel` — adding `"property"` is not needed; properties use `kind="method"`
- ThreadPoolExecutor in `parser_phase.py` parses files in parallel — the C# parser instance must be thread-safe (it is, if stateless like the existing ones)
- Parser instances cached in `_PARSER_CACHE` per language key — the C# parser factory just needs to be added to `_PARSER_FACTORIES`

### Integration Points
- `languages.py::SUPPORTED_EXTENSIONS` — extension point 1 (one-line add)
- `parser_phase.py::_PARSER_FACTORIES` — extension point 2 (one-line add)
- `base.py::SymbolInfo` — `properties: dict` field to be added (default empty dict, backward-compatible)
- `parser_phase.py` — second-pass collision detection for namespace qualification hooks in after the parallel parse loop

</code_context>

<specifics>
## Specific Ideas

- No specific "it should feel like X" references — follow the existing Python parser pattern closely
- Namespace-qualified collision resolution: the second pass in `parser_phase.py` renames conflicting nodes before they enter the graph

</specifics>

<deferred>
## Deferred Ideas

- Unity lifecycle method exemptions from dead-code — Phase 5
- C# partial class merging — Phase 5
- `[SerializeField]` / `[Header]` / `[RequireComponent]` Unity attribute handling for dead-code exemptions — Phase 5

</deferred>

---

*Phase: 01-c-parser-foundation*
*Context gathered: 2026-03-23*
