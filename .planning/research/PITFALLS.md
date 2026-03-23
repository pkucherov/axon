# Domain Pitfalls: Multi-Language Parser Integration

**Domain:** Code intelligence engines + tree-sitter multi-language parsing
**Researched:** 2026-03-23

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Incomplete Import Resolution Across Languages

**What goes wrong:**
C# uses `using Foo.Bar;` (module-level). C++ uses `#include "path.h"` (file-level). AngelScript uses `import;` or include patterns. If import resolution doesn't map correctly per-language, the graph becomes disconnected. Call graph becomes useless because callers can't find callees.

**Why it happens:**
Assuming all languages import the same way. Copy-pasting Python/TypeScript import logic without accounting for language-specific path resolution (C# assembly names vs C++ file paths vs AngelScript module paths).

**Consequences:**
- IMPORTS edges missing or incorrect
- CALLS edges fail to resolve (function "not found")
- Dead-code detection marks exported functions as dead (false positive)
- Users lose trust in impact analysis

**Prevention:**
- Per-language import resolution strategy documented in `imports.py` phase
- Test import resolution on real projects before declaring victory
- Validate that cross-file calls are correctly traced

**Detection:**
- FTS search returns function but graph traversal finds 0 incoming edges
- Manual spot-check: pick a known-called function, verify CALLS relationships exist

---

### Pitfall 2: Unhandled UE5 Macro Preprocessing

**What goes wrong:**
C++ macros (UCLASS, UFUNCTION, UPROPERTY) are preprocessor directives, not part of tree-sitter's C++ grammar. If not handled explicitly, they appear as unknown syntax or get dropped silently. Symbol metadata (Blueprint exposure, module membership) is lost.

**Why it happens:**
Assuming tree-sitter parses C++ "as-is" with macro support. Tree-sitter does NOT expand macros; it parses the literal token stream. Macros only exist in preprocessor.

**Consequences:**
- Dead-code detection flags BlueprintCallable functions as dead (wrong)
- Cannot build module dependency graph from .Build.cs
- UE5-specific metadata never reaches the graph
- Users say "Axon doesn't understand UE5"

**Prevention:**
- Implement explicit macro extraction layer (regex or AST inspection before tree-sitter)
- Store extracted macros in SymbolInfo.properties before creating graph nodes
- Test on UE5 sample code: verify UFUNCTION macros visible in graph properties
- Document macro extraction strategy and limitations

**Detection:**
- UE5 project indexed; query for UFUNCTION macros returns empty
- Blueprint-callable function is flagged dead (when it shouldn't be)

---

### Pitfall 3: Inconsistent Dead-Code Exemption Logic Across Languages

**What goes wrong:**
Dead-code exemptions added for UE5 (Blueprint flags) and Unity (lifecycle methods) but not tested thoroughly. Some exemptions fire only for specific languages or symbol kinds, leading to false positives. Changing exemption rules later requires re-parsing entire codebase.

**Why it happens:**
Premature optimization: adding exemptions in parsers instead of dead_code.py. Or: exemption logic tightly coupled to one language, breaks when new parser added.

**Consequences:**
- False positives: Unity Start() method flagged dead
- Users distrust dead-code results
- Every exemption change requires full re-index
- Difficult to audit exemption rules (scattered across multiple files)

**Prevention:**
- All exemption logic in dead_code.py only (centralized)
- Parsers extract facts (decorators, attributes, macros) into properties
- Write exemption predicates as pure functions
- Test exemptions on representative code for each language
- Document exemption rules in docstring

**Detection:**
- Test suite fails: test_ue5_blueprint_callable_not_dead
- Manual inspection: Blueprint function appears in dead-code results

---

## Moderate Pitfalls

### Pitfall 4: Over-Engineering Shared Parser Base Classes

**What goes wrong:**
Creating a UE5ParserBase class to share logic between CppUE5Parser and AngelScriptParser. Each language has different AST structures, so the base class requires awkward type conversions and conditional logic. Maintenance burden increases; hard to test in isolation.

**Why it happens:**
DRY principle applied too aggressively. Desire to avoid code duplication leads to premature abstraction.

**Consequences:**
- Base class becomes harder to understand (multiple languages + branches)
- Subclasses less readable (wrapping abstract methods)
- Debugging harder (extra layer of indirection)
- Sharing becomes coupling; change one parser, fear breaking the other

**Prevention:**
- Keep parsers fully independent
- Share logic via utility functions in ue5_utils.py, not inheritance
- Duplication is acceptable if it keeps code simpler
- Test each parser in isolation

**Detection:**
- Parser inheritance chain 2+ levels deep
- More than 3 conditional checks on language type in shared code

---

### Pitfall 5: Weak Test Coverage on Macro Extraction

**What goes wrong:**
Regex-based macro extraction (for UFUNCTION, UCLASS) is fragile. Edge cases (multiline macros, nested parentheses, macro arguments with commas) cause incorrect parsing. Tests only cover happy path, so regressions appear in production.

**Why it happens:**
Regex is fast to implement, tempting to skip edge-case tests. "We're just storing metadata anyway, not executing it."

**Consequences:**
- Silent data loss: macro flags stored incorrectly
- Dead-code exemptions don't fire (false positives)
- User debugging nightmare: "why is this BlueprintCallable function marked dead?"

**Prevention:**
- Comprehensive regex test suite: simple macros, nested, multiline, with/without arguments
- Test against real UE5 codebase (available per PROJECT.md)
- Document regex limitations in code comment
- If regex becomes unmaintainable, consider fallback to lightweight AST inspection

**Detection:**
- Regex test coverage <80%
- Macro extraction fails on real UE5 project samples

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|-----------|
| Phase 1: C# parsing | Attribute extraction incomplete | Write comprehensive regex tests; validate on real Unity projects |
| Phase 2: UE5 C++ parsing | Macro extraction regexes fail on multiline macros | Test regex extensively; have fallback minimal strategy |
| Phase 2: Dead-code exemptions | Blueprint detection false negatives | Manual testing on UE5 sample; audit all UFUNCTION invocations |
| Phase 3: AngelScript | Grammar unavailable; fallback regex too simple | Decide early: tree-sitter or regex fallback; test on representative code |
| General: Integration testing | Import resolution fails cross-language | Test on real multi-language projects; spot-check call graph |
| General: Performance | Indexing slower than Python/TypeScript baseline | Profile macro extraction; cache parser instances |

---

*Pitfall research: 2026-03-23*
