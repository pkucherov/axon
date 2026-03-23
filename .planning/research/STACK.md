# Technology Stack: C#, UE5 C++, AngelScript Parsers

**Project:** Axon Language Extension (C#, UE5 C++, AngelScript)
**Researched:** 2026-03-23
**Confidence:** MEDIUM (tree-sitter-cpp/-c-sharp HIGH, AngelScript ecosystem LOW)

---

## Executive Summary

Axon needs three parser additions:

1. **C#** (RECOMMENDED): `tree-sitter-c-sharp` v0.23.1 - production-ready, PyPI available
2. **C++** (RECOMMENDED): `tree-sitter-cpp` v0.23.4 - production-ready, PyPI available
3. **AngelScript** (COMPLEX): No official Python binding; needs custom integration

---

## Recommended Stack

### Core Parsing Libraries

| Technology | Version | Why |
|------------|---------|-----|
| tree-sitter-c-sharp | >=0.23.1 | Production-ready, 590 commits, 37 contributors, 421 dependents; C# 1-13.0 |
| tree-sitter-cpp | >=0.23.4 | Production-ready, 442 commits, 36 contributors, 1.1k dependents; C++11-20 |
| tree-sitter-angelscript | Custom | Active grammar (Relrin v0.2.0), 135 tests; no pre-built PyPI; requires binding |

---

## C# Details

**Status:** Production-ready

**Key Facts:**
- Released November 11, 2024
- Supports C# 1.0-13.0
- Based on official Roslyn grammar
- Known limit: async/var/await edge case in identifiers

**Python Integration:**
```python
import tree_sitter_c_sharp
from tree_sitter import Language, Parser
LANGUAGE = Language(tree_sitter_c_sharp.language())
```

**Unity Integration:** NOT built-in; requires manual exemptions for lifecycle methods
(Awake, Start, Update, LateUpdate, OnDestroy, etc.)

**Confidence:** HIGH

---

## C++ Details

**Status:** Production-ready

**Key Facts:**
- Released November 11, 2024
- Supports C++11-20, partial C++23
- Inherits preprocessor handling from tree-sitter-c
- NO special handling for UE5 macros

**UE5 Macro Strategy:**
- Tree-sitter parses UCLASS(), UFUNCTION(), UPROPERTY() as preprocessor nodes
- Post-parse scanning extracts metadata, stores in SymbolInfo.decorators
- Dead-code detection exempts symbols with UE5 metadata

**Confidence:** HIGH for C++; MEDIUM for UE5 macro extraction (post-parse required)

---

## AngelScript Details

**Status:** Requires custom binding

**Best Grammar:** Relrin/tree-sitter-angelscript v0.2.0
- 135 tests, full syntax coverage
- Actively maintained, BSD-3-Clause
- Rust/Node.js bindings only; NO Python

**Path A - Custom Binding (RECOMMENDED):**
- Build Python binding from Relrin grammar
- Publish to PyPI
- Effort: 2-3 weeks

**Path B - Custom Parser (FALLBACK):**
- Write regex/state-machine parser in Python
- Effort: 3-4 weeks

**Confidence:** Grammar HIGH; Python integration MEDIUM

---

## Integration Points

### Parser Registration (parser_phase.py)
```python
from axon.core.parsers.csharp import CSharpParser
from axon.core.parsers.cpp import CppParser
from axon.core.parsers.angelscript import AngelScriptParser

_PARSER_FACTORIES = {
    "python": PythonParser,
    "typescript": lambda: TypeScriptParser("typescript"),
    "csharp": CSharpParser,      # NEW
    "cpp": CppParser,             # NEW
    "angelscript": AngelScriptParser,  # NEW
}
```

### Language Registration (languages.py)
```python
SUPPORTED_EXTENSIONS = {
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".as": "angelscript",
}
```

---

## Known Issues

### Issue 1: UE5 Macros Not Expanded
- Tree-sitter parses as preprocessor directives, not semantic metadata
- Workaround: Post-parse regex scanning stores in decorators list
- Dead-code detection exempts UE5-annotated symbols

### Issue 2: AngelScript No Official Binding
- Relrin grammar mature but no PyPI
- Solution: Build custom binding (2-3 weeks)

### Issue 3: Limited C++ Semantic Analysis
- Cannot resolve templates across files
- Mitigation: Existing Axon import phase handles cross-file linking

---

## First Steps

1. Implement C# and C++ parsers (2-3 days each) - both PyPI ready
2. Spike AngelScript binding (3-5 days)
3. Extend dead-code detection for UE5/Unity metadata (1 week)
4. Validate on real UE5/Unity codebases

---

**Research Date:** 2026-03-23
