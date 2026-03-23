# Research Summary: Language Extension (C#, UE5 C++, AngelScript)

**Project:** Axon Language Extension: C#, UE5 C++, AngelScript Parsers
**Domain:** Code intelligence engine language parser extension
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH (tree-sitter grammars validated; UE5 semantics from public sources; AngelScript ecosystem fragmented)

---

## Executive Summary

Adding three new language parsers to Axon is architecturally straightforward because the parser abstraction is language-agnostic. All three parsers must emit the same `ParseResult` dataclass, allowing existing downstream phases (dead-code detection, call graphs, heritage analysis) to operate unchanged.

The recommended approach leverages **production-ready tree-sitter grammars for C# and C++** with post-parse macro extraction for UE5 metadata (UCLASS, UFUNCTION, UPROPERTY). **AngelScript poses the highest risk** — while the Relrin grammar is mature, it has no official Python binding; building a custom binding adds 2-3 weeks but is the recommended path over a fragile regex-based parser. The critical success factor is **capturing UE5 macro metadata without separate graph nodes** — store decorators in `properties` dict on symbols, avoiding graph bloat while keeping dead-code exemptions centralized in `dead_code.py`.

**Key risk:** UE5 macro extraction via regex is fragile and prone to silent data loss on edge cases (multiline macros, nested parentheses). This must be validated early against real UE5 code and tested comprehensively. **Mitigation:** Phase 2 includes a spike validating macro extraction on real UE5 headers before declaring victory.

---

## Key Findings

### Recommended Stack

Research confirms three language parsers with clear rationale:

**Core technologies:**
- **tree-sitter-c-sharp** v0.23.1+ — Production-ready, 590 commits, 37 contributors, 421 dependents; supports C# 1.0–13.0 syntax; published to PyPI
- **tree-sitter-cpp** v0.23.4+ — Production-ready, 442 commits, 36+ contributors, 1.1K dependents; C++11–20 support; inherits preprocessor handling from tree-sitter-c
- **tree-sitter-angelscript** (custom binding) — Relrin v0.2.0 grammar is most mature (135 tests, full syntax coverage, actively maintained); no Python binding exists; recommend building custom binding (2-3 weeks) over regex fallback

**Integration pattern:** Each parser registers in `parser_phase.py:_PARSER_FACTORIES` and maps file extensions in `languages.py`. No new KuzuDB schema required — all metadata stored in existing `properties: JSON` column on graph nodes.

### Expected Features

Research identifies feature dependencies critical to graph coherence:

**Must have (table stakes for all three languages):**
- Function/method extraction — core symbol type; dead-code graph cannot exist without
- Class extraction — organizing unit; required for EXTENDS/IMPLEMENTS edges
- Type references — parameter/return types; feeds type-ref edges and dead-code checks
- Imports — dependency resolution; module navigation; cross-file call tracing
- Calls — call graph foundation; dead-code depends on incoming CALLS edges
- Inheritance — EXTENDS/IMPLEMENTS relationships feed dead-code and community detection

**Should have (game engine differentiators):**
- **C# Unity lifecycle exemption** — MonoBehaviour methods (Start, Update, etc.) never dead; false positives otherwise
- **UE5 Blueprint exposure detection** — BlueprintCallable, BlueprintEvent, BlueprintNativeEvent functions never flagged dead
- **UE5 macro extraction** — UCLASS/UFUNCTION/UPROPERTY metadata as decorators; prevents false dead-code positives
- **UE5 base class registry** — AActor, UObject, UActorComponent never flagged missing; hardcoded registry in dead_code.py
- **Module nodes (.Build.cs)** — Deferred but planned; module dependencies with DEPENDS_ON edges

**Defer (v2+):**
- Full UHT (Unreal Header Tool) simulation — too complex; store as opaque metadata
- C# .NET Standard Library registry — add incrementally as false positives emerge
- AngelScript vanilla (non-UE5) support — focus on UnrealAngel dialect only in v1
- Template/generic specialization — complex; keep generics unseparated

### Architecture Approach

Adding three new language parsers requires minimal architectural changes. The `LanguageParser` protocol is language-agnostic; new parsers simply implement `parse(content, file_path) -> ParseResult` and register in the parser factory. **Critical design decisions:**

1. **No new NodeLabel enum entries** — Use existing FUNCTION, CLASS, METHOD, INTERFACE, ENUM labels; store UE5 metadata in `properties` dict
2. **Shared utilities in `ue5_utils.py`** — UE5 macro patterns, Blueprint detection predicates, base class registry; keep parsers independent (no inheritance)
3. **All dead-code exemptions in `dead_code.py`** — Centralized, language-agnostic, easily auditable; parsers extract facts, dead_code decides significance
4. **No MODULE node in v1** — .Build.cs can be parsed as C++ with metadata in properties; defer MODULE node type and DEPENDS_ON edges to Phase 2 milestone end
5. **Build order: C# → UE5 C++ → AngelScript** — C# has lowest complexity (no macros); establishes parser pattern; UE5 C++ is most complex; AngelScript highest risk (grammar uncertainty)

**Major components:**
1. **Parser layer** — Three independent LanguageParser implementations; each walks tree-sitter AST, accumulates ParseResult
2. **Configuration layer** — `languages.py` extension→language mappings; `parser_phase.py` factory registration
3. **Dead-code exemption layer** — Extended `dead_code.py` + `ue5_utils.py` for Blueprint/lifecycle/base-class checks

### Critical Pitfalls

Research identifies five pitfalls that cause major rework or user distrust:

1. **Incomplete import resolution across languages** — C# uses `using Foo.Bar;` (module-level); C++ uses `#include "path.h"` (file-level); AngelScript uses dialect-specific imports. If not handled per-language, IMPORTS edges are missing, CALLS edges fail to resolve, dead-code falsely flags exported functions. **Mitigation:** Document language-specific import resolution in `imports.py` phase; test on real projects before release; validate cross-file calls.

2. **Unhandled UE5 macro preprocessing** — Tree-sitter does NOT expand macros; UCLASS/UFUNCTION appear as preprocessor nodes only. If not extracted explicitly, Symbol metadata (Blueprint exposure, module membership) is lost; dead-code flags BlueprintCallable functions as dead. **Mitigation:** Implement explicit macro extraction (regex or AST inspection before tree-sitter); store in SymbolInfo.properties; test on real UE5 headers; document limitations.

3. **Inconsistent dead-code exemption logic** — Exemptions added in parsers instead of dead_code.py, or tightly coupled to one language, leading to false positives. Every exemption change then requires full re-index. **Mitigation:** All exemption logic in dead_code.py only (centralized); parsers extract facts (decorators, attributes, macros); write exemption predicates as pure functions; test on representative code per language.

4. **Over-engineering shared parser base classes** — Creating UE5ParserBase class leads to awkward type conversions, increased maintenance burden, hard-to-test shared logic. **Mitigation:** Keep parsers fully independent; share logic via utility functions in ue5_utils.py, not inheritance; duplication is acceptable.

5. **Weak test coverage on macro extraction** — Regex-based UFUNCTION/UCLASS extraction is fragile; edge cases (multiline, nested parentheses, comma-separated args) cause incorrect parsing; tests skip edge cases. **Mitigation:** Comprehensive regex test suite covering simple, nested, multiline, with/without arguments; test against real UE5 codebase; document regex limitations; fallback strategy if regex unmaintainable.

---

## Implications for Roadmap

Based on research, **six phases** are suggested with clear dependencies and research flags.

### Phase 1: C# Baseline Parsing
**Rationale:** Lowest complexity; no macro preprocessing; establishes parser pattern for downstream phases; validates parser architecture and testing methodology.

**Delivers:**
- CSharpParser implementation extracting functions, methods, classes, interfaces, properties, enums
- Attribute capture (e.g., [SerializeField], [Header]) stored in `properties["attributes"]`
- .cs file support; registration in `parser_phase.py` and `languages.py`
- Comprehensive test suite (80+ cases): symbol extraction, attribute capture, inheritance

**Addresses:** Table stakes features — Functions, Methods, Classes, Interfaces, Properties, Imports, Type References, Inheritance, Calls, Modifiers

**Avoids:** Pitfall 4 (over-engineering); Pitfall 1 (incomplete imports)

**Research flags:** None — tree-sitter-c-sharp is mature, grammar well-documented

### Phase 2: UE5 C++ Parsing + Dead-Code Exemptions
**Rationale:** Most complex parser; depends on Phase 1 pattern established; enables UE5-specific dead-code exemptions; critical risk area (macro extraction fragility).

**Delivers:**
- CppUE5Parser extracting functions, methods, classes, structs, enums from .h/.cpp files
- UE5 macro extraction (UCLASS, UFUNCTION, UPROPERTY) via post-parse regex scanning; stored in `properties["ue5_macros"]`
- `ue5_utils.py` module: UE5 macro patterns, Blueprint detection predicates, base class registry (AActor, UObject, ACharacter, etc.)
- Extended `dead_code.py`: Blueprint exposure detection, UE5 base class exemptions
- .h, .cpp, .Build.cs file support; registration in parser_phase.py and languages.py
- Comprehensive test suite (100+ cases): symbol extraction, macro capture, Blueprint detection

**Uses:** tree-sitter-cpp, `ue5_utils.py`, `dead_code.py`

**Avoids:** Pitfall 2 (unhandled macro preprocessing); Pitfall 3 (inconsistent exemptions); Pitfall 5 (weak macro test coverage)

**Research flags:**
- **High priority:** Validate macro extraction regex patterns on real UE5 headers; test edge cases (multiline, nested parentheses); consider fallback strategy if regex insufficient
- **Medium priority:** Confirm .Build.cs file structure contains module dependencies; finalize MODULE node integration strategy (defer or include in Phase 2?)

### Phase 3: AngelScript Parsing
**Rationale:** Highest risk; grammar uncertainty; depends on UE5 utilities from Phase 2; reuses dead-code exemption patterns; smallest scope if fallback regex parser needed.

**Delivers:**
- AngelScriptParser extracting functions, methods, classes from .as files
- Grammar choice validation: Confirm tree-sitter-angelscript (or alternative) exists, is maintained, and extracts symbols correctly
- UE5 annotation handling (e.g., @BlueprintCallable or UFUNCTION equivalents); stored in `properties["ue5_annotations"]`
- .as file support; registration in parser_phase.py and languages.py
- Comprehensive test suite (80+ cases): symbol extraction, UE5 annotation capture, inheritance

**Uses:** tree-sitter-angelscript (or custom binding if tree-sitter unavailable), `ue5_utils.py`, `dead_code.py`

**Avoids:** Pitfall 5 (weak test coverage); Pitfall 1 (incomplete imports)

**Research flags:**
- **High priority:** Validate tree-sitter-angelscript grammar; inspect grammar.js for symbol extraction capability; test on real UnrealAngel code
- **Medium priority:** Confirm UnrealAngel dialect and UFUNCTION-like macro syntax; document assumptions

### Phase 4: Unity Lifecycle Exemptions
**Rationale:** Depends on C# parser (Phase 1); C# deadcode exemptions are separable from parsing; medium complexity; directly improves false-positive rate on Unity codebases.

**Delivers:**
- Extended `dead_code.py`: Unity lifecycle method detection (Start, Update, Awake, OnEnable, OnDisable, etc.)
- MonoBehaviour inheritance detection; public methods on MonoBehaviour subclasses exempt from dead-code
- [SerializeField]/[Header] attribute integration; fields marked for editor serialization treated as API
- Comprehensive test suite: lifecycle method exemptions, MonoBehaviour detection, attribute handling

**Addresses:** Differentiators — Unity lifecycle exemption, [SerializeField] / [Header] detection

**Uses:** CSharpParser output, `dead_code.py`

**Avoids:** Pitfall 3 (inconsistent exemptions)

**Research flags:** None — Unity documentation is official; lifecycle methods are stable across versions

### Phase 5: Cross-Language Import Resolution Validation
**Rationale:** Depends on all three parsers (Phases 1–3); integration phase; critical for graph coherence; prevents Pitfall 1 (incomplete import resolution).

**Delivers:**
- Validation suite: test import resolution on multi-language projects
- Manual spot-checks on real C#/C++/AngelScript codebases; verify IMPORTS edges created
- Cross-file call tracing: pick known-called function, verify incoming CALLS edges exist
- Documentation: language-specific import resolution strategy per language

**Addresses:** Pitfall 1 — Prevent missing IMPORTS edges, incorrect CALLS resolution, false dead-code positives

**Uses:** All three parsers, `imports.py` phase

**Research flags:**
- **High priority:** Test on real multi-language projects; validate call graphs; spot-check import edges

### Phase 6: Module Nodes (.Build.cs Integration) [OPTIONAL, END OF MILESTONE]
**Rationale:** Lower priority; architectural feature; depends on UE5 C++ parser (Phase 2); complex .Build.cs format; deferred if time constrained.

**Delivers:**
- MODULE node type (`NodeLabel.MODULE`) added to model.py
- KuzuDB schema extended: `Module` table, `DEPENDS_ON` REL TABLE
- .Build.cs parsing logic in CppUE5Parser or separate `module_discovery.py` phase
- Module dependency extraction: PublicDependencyModuleNames, PrivateDependencyModuleNames
- MODULE and DEPENDS_ON edges in graph

**Addresses:** Differentiator — Architecture-level view; module-scoped dead code; project structure visible

**Uses:** CppUE5Parser output, new `module_discovery.py` phase, extended dead_code.py (don't flag MODULE-level exports as dead)

**Research flags:**
- **Medium priority:** Confirm .Build.cs file format (JSON-like, Python-like, or other); validate against real UE5 projects; finalize MODULE node semantics

### Phase Ordering Rationale

1. **C# first (Phase 1):** Lowest complexity establishes parser pattern; unblocks Phase 2
2. **UE5 C++ second (Phase 2):** More complex; depends on C# pattern; enables `ue5_utils.py` for Phase 3
3. **AngelScript third (Phase 3):** Highest risk; depends on UE5 utils; can reuse patterns
4. **Unity exemptions fourth (Phase 4):** Separable from parsing; improves C# false positives
5. **Cross-language validation fifth (Phase 5):** Depends on all parsers; integration phase
6. **Module nodes sixth (Phase 6):** Optional; lower priority; complete architecture

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** UE5 macro extraction accuracy — validate regex patterns on real UE5 headers; test edge cases; have fallback strategy
- **Phase 2:** .Build.cs file structure — confirm module dependencies exist; design MODULE node integration strategy
- **Phase 3:** AngelScript grammar availability — verify community grammar works; test on real UnrealAngel code; decide between tree-sitter or custom parser
- **Phase 5:** Cross-language import resolution — test on multi-language projects; spot-check call graphs

Phases with standard patterns (skip research-phase):
- **Phase 1:** C# parsing — tree-sitter-c-sharp is official grammar; attribute extraction is first-class AST
- **Phase 4:** Unity lifecycle methods — official Unity documentation; method names are stable; hardcoded list is robust

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | tree-sitter-c-sharp (v0.23.1+) and tree-sitter-cpp (v0.23.4+) are production-ready, well-maintained, published to PyPI; confirmed from public GitHub repos. AngelScript has mature Relrin grammar but no Python binding (MEDIUM on binding feasibility; 2-3 weeks effort estimated) |
| **Features** | MEDIUM-HIGH | C# and C++ table stakes confirmed via tree-sitter grammar inspection; UE5 Blueprint specifiers and base classes from public UE5 documentation; Unity lifecycle methods from official Unity docs (HIGH). AngelScript feature set based on angelcode.com manual + community grammars (MEDIUM; needs validation on UnrealAngel dialect) |
| **Architecture** | MEDIUM-HIGH | Parser pattern mirrors existing Python/TypeScript parsers (HIGH). Dead-code exemption strategy is sound but unproven on UE5 macro edge cases (MEDIUM). MODULE node deferral is reasonable but .Build.cs format needs validation (MEDIUM) |
| **Pitfalls** | MEDIUM | Pitfalls 1–3 are well-known in multi-language parser projects (MEDIUM confidence from general knowledge). Pitfalls 4–5 are specific to shared code design; validation during Phase 2 macro spike will clarify (MEDIUM) |

**Overall confidence: MEDIUM-HIGH** — Stack and feature landscape are well-researched; architecture pattern is sound; main uncertainties are UE5 macro extraction fragility, AngelScript grammar choice, and .Build.cs module parsing complexity.

### Gaps to Address

- **AngelScript grammar verification:** Five community tree-sitter grammars exist; unclear which is best for UnrealAngel. **Mitigation:** Phase 3 spike includes grammar inspection and test on real UnrealAngel code.
- **UE5 macro extraction edge cases:** Regex-based extraction may fail on multiline macros, nested parentheses, or newer UE5 macro patterns. **Mitigation:** Phase 2 spike validates regex on real UE5 headers; fallback strategy if insufficient.
- **C# import resolution mapping:** How `using System.X` maps to module paths unclear without test on real project. **Mitigation:** Phase 1 validation includes import resolution tests.
- **.Build.cs file structure:** Unclear if modules should be separate nodes or metadata on C++ classes. **Mitigation:** Phase 2 spike validates .Build.cs format; defer MODULE node type if structure complex.
- **Cross-language call graph coherence:** Import resolution fragility may cause CALLS edge misses across languages. **Mitigation:** Phase 5 validation includes spot-checks on real multi-language projects.

---

## Sources

### Primary (HIGH Confidence)

- **tree-sitter-c-sharp** (GitHub: tree-sitter/tree-sitter-c-sharp) — Grammar inspection confirmed C# 1.0–13.0 support; 590 commits, 37 contributors; v0.23.1 released Nov 2024
- **tree-sitter-cpp** (GitHub: tree-sitter/tree-sitter-cpp) — Grammar inspection confirmed C++11–20 support; 442 commits, 36+ contributors; v0.23.4 stable
- **Unity MonoBehaviour Documentation** (https://docs.unity3d.com/ScriptReference/MonoBehaviour.html) — Official lifecycle method enumeration (HIGH confidence; stable across Unity versions)
- **UE5 Macro Documentation** (Public UE5 development forums, engine source) — UCLASS, UFUNCTION, UPROPERTY specifiers widely documented (HIGH on core list; MEDIUM on version-specific variations)
- **UE5 Base Classes** (Unreal Engine 5 source, public API) — AActor, UObject, APawn, ACharacter, etc. are stable core classes (HIGH confidence)

### Secondary (MEDIUM Confidence)

- **tree-sitter-angelscript** (GitHub: Relrin/tree-sitter-angelscript) — Grammar v0.2.0 is most mature (135 tests, full syntax); no official Python binding (MEDIUM confidence; binding feasibility ~2-3 weeks)
- **AngelScript Home** (https://www.angelcode.com/angelscript/) — Official manual; language features documented (MEDIUM confidence; manual not fully accessible online)
- **Hazelight UnrealAngel** (Game dev forums, community references) — UE5 AngelScript fork exists but underdocumented (LOW-MEDIUM confidence; needs empirical validation)

### Tertiary (LOW Confidence)

- **Community tree-sitter grammars for AngelScript** — Five implementations on GitHub; unclear which is best for UnrealAngel (LOW confidence; requires validation during Phase 3)

---

**Research completed: 2026-03-23**
**Ready for roadmap: yes**
**Roadmap implications:** Six phases suggested; Phase 1–3 are critical path (parsers); Phase 4–5 are validation/exemptions; Phase 6 (MODULE nodes) is optional end-of-milestone enhancement.
