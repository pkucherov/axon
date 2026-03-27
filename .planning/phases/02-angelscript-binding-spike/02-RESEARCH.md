# Phase 2: AngelScript Binding Spike — Research

**Researched:** 2026-03-27
**Domain:** tree-sitter grammar evaluation, Python C-extension wheel packaging
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Evaluate both `Relrin/tree-sitter-angelscript` and `dimitrijejankov/tree-sitter-unreal-angelscript`. Test both against sample UnrealAngel AngelScript files. Pick the grammar with better UE5/UnrealAngel construct coverage.
- **D-02:** Use the Hazelight VS Code extension (`Hazelight/vscode-unreal-angelscript`) as the authoritative reference for UnrealAngel AngelScript syntax. The Hazelight parser uses PEGGY — extract grammar rules as the source of truth when evaluating coverage gaps and when extending the chosen grammar.
- **D-03:** If the better grammar has gaps after evaluation, fork it into `third-party/` and extend `grammar.js` using the Hazelight PEGGY grammar as the reference spec. Do NOT fall back to a regex-based parser.
- **D-04:** Build a proper Python wheel that exposes a `.language()` function returning a `PyCapsule`, matching the exact import pattern: `import tree_sitter_angelscript as tsas; AS_LANGUAGE = Language(tsas.language())`
- **D-05:** Vendor the chosen grammar under `third-party/tree-sitter-angelscript/` at the repo root.
- **D-06:** Add a local path dependency to `pyproject.toml`: `"tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript"`. Running `uv sync` must build and install automatically.
- **D-07:** The spike test must prove the grammar can parse: (1) function declarations, (2) class declarations with inheritance, (3) UE5-style annotations (UCLASS, mixin, UFUNCTION-equivalent), (4) #include/import directives. Any failure requires grammar extension before Phase 4.
- **D-08:** Phase 4 is blocked on this spike completing with a committed, importable binding.

### Claude's Discretion

- Which grammar (Relrin vs dimitrijejankov) is ultimately selected
- Exact Python package name in pyproject.toml
- Grammar extension scope — which rules need to be added or patched to meet D-07
- Test sample file content for spike validation tests

### Deferred Ideas (OUT OF SCOPE)

- AngelScript parser implementation (Phase 4)
- Registering `.as` in `languages.py` and `_PARSER_FACTORIES` (Phase 4)
- UE5 annotations extraction logic (Phase 4)
- Publishing the AngelScript wheel to PyPI (post-v1)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-06 | Build or vendor a Python binding for `Relrin/tree-sitter-angelscript` and integrate it into the project | Grammar evaluation findings, binding scaffold pattern, pyproject.toml path-dep mechanism |
</phase_requirements>

---

## Summary

The AngelScript binding spike has one job: deliver a Python-importable wheel exposing `language()` → `PyCapsule` so Phase 4 can do `Language(tsas.language())`. The canonical pattern for this is well-established — every tree-sitter grammar on PyPI uses an identical `binding.c` + `setup.py` + Python package scaffold. Replicating it for a vendored grammar is mechanical once the grammar source is in hand.

The two candidate grammars diverge sharply on UE5 coverage. `dimitrijejankov/tree-sitter-unreal-angelscript` was built specifically for UnrealAngel — it has `uclass_macro`, `ufunction_macro`, `uproperty_macro`, `ustruct_macro`, `uenum_macro` as first-class nodes, corpus tests for each, and handles the `UCLASS(BlueprintType) class AMyActor : AActor {}` pattern verbatim. `Relrin/tree-sitter-angelscript` covers generic AngelScript (standard import syntax, mixin, class, func) but has zero UE5 macro awareness. The choice is clear: dimitrijejankov is the primary candidate.

The one gap in dimitrijejankov: it has **no Python binding scaffold** — only `bindings/node/` and `bindings/rust/`. The plan must create `bindings/python/` from scratch following the canonical pattern (binding.c + `__init__.py` + `setup.py`). This is about 60 lines of boilerplate that can be copied almost verbatim from `tree-sitter-python`. The grammar's `src/parser.c` already exists and does not require a scanner.c (confirmed: no external scanner in dimitrijejankov). The only question is whether `tree-sitter-cli` is needed to regenerate `parser.c` — it is not needed if we vendor the pre-generated `src/parser.c` as-is.

**Primary recommendation:** Vendor `dimitrijejankov/tree-sitter-unreal-angelscript` into `third-party/tree-sitter-angelscript/`, add `bindings/python/` scaffold, wire as a path dependency in `pyproject.toml`. If Hazelight coverage comparison reveals gaps (e.g. `#include` preprocessor directives), extend `grammar.js` and regenerate `parser.c` using `npx tree-sitter generate` (Node 24 is available).

---

## Grammar Evaluation

### Candidate 1: dimitrijejankov/tree-sitter-unreal-angelscript

**Confidence: HIGH** (verified by fetching grammar.js and corpus/ tests)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Class declarations with inheritance | PASS | corpus/classes.txt: `class AMyActor : AActor {}` |
| UCLASS macro | PASS | `uclass_macro` rule; corpus/macros.txt |
| UFUNCTION macro | PASS | `ufunction_macro` rule; corpus/macros.txt |
| UPROPERTY macro | PASS | `uproperty_macro` rule |
| USTRUCT / UENUM macros | PASS | `ustruct_macro`, `uenum_macro` rules |
| Method declarations | PASS | `function_declaration` inside class body |
| Global function declarations | PASS | `global_function_declaration` rule |
| Mixin functions | PASS | `optional(choice("mixin", "local"))` in global_function_declaration |
| Import statements | PASS | `import_statement` rule |
| Preprocessor directives | PASS | `preprocessor_directive: token(seq("#", /[^\r\n]*/))` |
| Python binding scaffold | MISSING | Only `bindings/node/` and `bindings/rust/` |
| External scanner | NONE | `src/` has only `parser.c`, `grammar.json`, `node-types.json` |
| tree-sitter.json | PRESENT | Scopes `.as` files |
| Corpus tests | 14 files | access, advanced_macros, classes, delegates, expressions, functions, literals, loops, macros, namespaces, parameters, preprocessor, simple, statements |
| tree-sitter-cli version | 0.20.0 | Older; pre-generated `src/parser.c` already committed — no regeneration needed for vendoring |

**Coverage gap identified:** `#include` directives. The `preprocessor_directive` rule matches `#` followed by any non-newline characters — this is a catch-all that will parse `#include "SomeFile.as"` as a `preprocessor_directive` node but does NOT expose the include path as a structured child. Phase 4 will need to extract the path via string manipulation on the node text. This is acceptable — document it in coverage notes.

### Candidate 2: Relrin/tree-sitter-angelscript

**Confidence: HIGH** (verified by fetching grammar.js)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Class declarations with inheritance | PASS | `class_declaration` rule |
| UCLASS macro | FAIL | No macro rules at all |
| UFUNCTION macro | FAIL | No macro rules at all |
| Import statements | PARTIAL | `import_declaration` uses `from "source"` syntax — standard AS, not UnrealAngel style |
| External scanner | YES | Has `src/scanner.c` — adds complexity to Python build |
| Python binding scaffold | MISSING | No `bindings/python/` |

**Verdict:** Relrin lacks UE5 macro support entirely. It requires an external scanner (C source, more complex build). Do NOT use Relrin as the primary grammar. D-01 is resolved: use dimitrijejankov.

### Hazelight PEGGY Grammar (authoritative reference)

**Confidence: MEDIUM** (verified by fetching partial grammar source)

The Hazelight `language-server/pegjs/angelscript.pegjs` confirms these UnrealAngel-specific constructs:
- `UCLASS`, `UFUNCTION` as keywords
- `mixin` keyword in function scope
- `import_statement` using dot-separated identifiers
- `class_declaration` with `:`-based inheritance
- `comment_documentation` for doc-comment decorators

The Hazelight grammar aligns with dimitrijejankov's coverage for the D-07 criteria. The Hazelight grammar is the spec for any grammar extensions needed in Phase 2 (use it to guide adding structured `#include` parsing if required).

---

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| tree-sitter (Python) | 0.25.2 (installed) | Parse trees, Language/Parser API | Already pinned in project |
| setuptools | >=62.4.0 | Build C extension wheel | Required by canonical tree-sitter binding pattern |
| wheel | latest | Build `.whl` artifact | Required by canonical pattern |

### Supporting

| Library/Tool | Version | Purpose | When to Use |
|---|---|---|---|
| Node.js | 24.13.0 (available) | Run `npx tree-sitter generate` | Only needed if grammar.js is extended |
| npx tree-sitter generate | CLI via npx | Regenerate parser.c from grammar.js | Required when grammar.js is modified |

**Installation (local wheel):**
```
# In pyproject.toml [project.dependencies]:
"tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript"

# Then:
uv sync
```

**No npm install needed.** `tree-sitter generate` is run via `npx` if grammar.js is modified. If grammar.js is NOT modified, the pre-generated `src/parser.c` in dimitrijejankov is used directly.

---

## Architecture Patterns

### Vendored Third-Party Wheel Structure

```
third-party/
└── tree-sitter-angelscript/
    ├── grammar.js                  # Vendored from dimitrijejankov (DO NOT MODIFY unless extending)
    ├── src/
    │   ├── parser.c                # Pre-generated; vendored as-is
    │   ├── grammar.json
    │   └── node-types.json
    ├── bindings/
    │   └── python/
    │       └── tree_sitter_angelscript/
    │           ├── __init__.py     # Exposes language() function
    │           ├── __init__.pyi    # Type stub
    │           ├── binding.c       # C extension; PyCapsule wrapper
    │           └── py.typed        # PEP 561 marker
    ├── pyproject.toml              # Build metadata (setuptools)
    └── setup.py                    # C extension build script
```

### Pattern 1: binding.c — PyCapsule Wrapper

This is the canonical pattern used by ALL tree-sitter grammar packages on PyPI (tree-sitter-python, tree-sitter-c-sharp, tree-sitter-cpp, etc.). Verified by inspecting `/h/Github/axon/.venv/Lib/site-packages/tree_sitter_c_sharp/binding.c`.

```c
// Source: tree-sitter-python binding.c (canonical pattern; identical across all grammars)
#include <Python.h>

typedef struct TSLanguage TSLanguage;

// Forward-declare the C function generated by tree-sitter
TSLanguage *tree_sitter_unreal_angelscript(void);

static PyObject* _binding_language(PyObject *Py_UNUSED(self), PyObject *Py_UNUSED(args)) {
    return PyCapsule_New(tree_sitter_unreal_angelscript(), "tree_sitter.Language", NULL);
}

static PyMethodDef methods[] = {
    {"language", _binding_language, METH_NOARGS,
     "Get the tree-sitter language for this grammar."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "_binding",
    .m_doc = NULL,
    .m_size = 0,
    .m_methods = methods,
};

PyMODINIT_FUNC PyInit__binding(void) {
    return PyModule_Create(&module);
}
```

**CRITICAL:** The function name in `tree_sitter_unreal_angelscript()` must match the `name:` field in `grammar.js`. For dimitrijejankov: `name: "unreal_angelscript"` → function is `tree_sitter_unreal_angelscript`. Verify this in `src/parser.c` first line.

### Pattern 2: `__init__.py` — Re-exports language()

```python
# bindings/python/tree_sitter_angelscript/__init__.py
"""UnrealAngel AngelScript grammar for tree-sitter."""

from ._binding import language

__all__ = ["language"]
```

### Pattern 3: `setup.py` — C Extension Build

```python
# setup.py (Windows-compatible MSVC + GCC dual path)
from os import path
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext

class BuildExt(build_ext):
    def build_extension(self, ext):
        if self.compiler.compiler_type != "msvc":
            ext.extra_compile_args = ["-std=c11", "-fvisibility=hidden"]
        else:
            ext.extra_compile_args = ["/std:c11", "/utf-8"]
        # dimitrijejankov has NO scanner.c — do NOT add it
        super().build_extension(ext)

setup(
    packages=find_packages("bindings/python"),
    package_dir={"": "bindings/python"},
    package_data={
        "tree_sitter_angelscript": ["*.pyi", "py.typed"],
    },
    ext_package="tree_sitter_angelscript",
    ext_modules=[
        Extension(
            name="_binding",
            sources=[
                "bindings/python/tree_sitter_angelscript/binding.c",
                "src/parser.c",
            ],
            define_macros=[
                ("PY_SSIZE_T_CLEAN", None),
                ("TREE_SITTER_HIDE_SYMBOLS", None),
            ],
            include_dirs=["src"],
        )
    ],
    cmdclass={"build_ext": BuildExt},
    zip_safe=False,
)
```

### Pattern 4: `pyproject.toml` for the vendored package

```toml
[build-system]
requires = ["setuptools>=62.4.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tree-sitter-angelscript"
version = "0.1.0"
description = "UnrealAngel AngelScript grammar for tree-sitter (vendored)"
requires-python = ">=3.11"
```

### Pattern 5: Axon's `pyproject.toml` path dependency

```toml
# In [project.dependencies], add after tree-sitter-cpp:
"tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript",
```

`uv sync` will call `pip install --no-build-isolation` on the local path, which invokes `setup.py` to compile `parser.c` and `binding.c` into `_binding.pyd` (Windows) or `_binding.so` (Linux/Mac). This is how all other tree-sitter grammar packages on PyPI are installed.

### Pattern 6: Spike test that validates grammar capability

```python
# tests/core/test_angelscript_binding.py
import pytest

def test_binding_importable():
    import tree_sitter_angelscript as tsas
    from tree_sitter import Language
    lang = Language(tsas.language())
    assert lang is not None

def test_parse_class_with_inheritance():
    import tree_sitter_angelscript as tsas
    from tree_sitter import Language, Parser
    lang = Language(tsas.language())
    parser = Parser(lang)
    source = b"UCLASS(BlueprintType)\nclass AMyActor : AActor\n{\n}"
    tree = parser.parse(source)
    # Must contain class_declaration with uclass_macro child and custom_type (AActor)
    assert tree.root_node.type == "program"
    classes = [n for n in tree.root_node.children if n.type == "class_declaration"]
    assert len(classes) == 1

def test_parse_ufunction():
    import tree_sitter_angelscript as tsas
    from tree_sitter import Language, Parser
    lang = Language(tsas.language())
    parser = Parser(lang)
    source = b"UFUNCTION(BlueprintCallable)\nvoid MyFunc()\n{\n}"
    tree = parser.parse(source)
    funcs = [n for n in tree.root_node.children if n.type == "global_function_declaration"]
    assert len(funcs) == 1

def test_parse_import():
    import tree_sitter_angelscript as tsas
    from tree_sitter import Language, Parser
    lang = Language(tsas.language())
    parser = Parser(lang)
    source = b"import MyModule.SomeFile"
    tree = parser.parse(source)
    imports = [n for n in tree.root_node.children if n.type == "import_statement"]
    assert len(imports) == 1

def test_parse_preprocessor_include():
    import tree_sitter_angelscript as tsas
    from tree_sitter import Language, Parser
    lang = Language(tsas.language())
    parser = Parser(lang)
    source = b'#include "SomeFile.as"'
    tree = parser.parse(source)
    directives = [n for n in tree.root_node.children if n.type == "preprocessor_directive"]
    assert len(directives) == 1
    # Path extraction requires text parsing — structured child nodes NOT expected
    assert b"SomeFile.as" in directives[0].text
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| C extension binding | Custom ctypes wrapper | Canonical binding.c + setup.py pattern | ctypes approach is fragile, no PyCapsule compatibility with tree-sitter Language API |
| Grammar parser | Regex-based AngelScript parser | dimitrijejankov grammar | D-03 explicitly forbids regex fallback; grammar already handles UE5 macros |
| parser.c generation | Running tree-sitter generate from scratch | Vendor pre-generated `src/parser.c` | tree-sitter-cli not installed, not needed if grammar.js unchanged |
| Tree walking utilities | Custom recursive walkers | tree-sitter Python API (`.children`, `.type`, `.text`) | Already works; same pattern as csharp_lang.py and python_lang.py |

**Key insight:** The binding scaffold is 60 lines of boilerplate copied from any existing tree-sitter grammar package. The grammar source (`src/parser.c`) is already pre-generated and committed in the repo. Nothing needs to be built from scratch.

---

## Common Pitfalls

### Pitfall 1: Wrong function name in binding.c

**What goes wrong:** `tree_sitter_unreal_angelscript()` is the C function name derived from `name: "unreal_angelscript"` in grammar.js. If binding.c uses `tree_sitter_angelscript()` instead, the linker will fail with an unresolved symbol error.

**Why it happens:** Renaming the Python package to `tree-sitter-angelscript` (dropping "unreal") is sensible, but the C symbol name comes from grammar.js `name:` field, not the package name.

**How to avoid:** Before writing binding.c, grep `src/parser.c` line 1 for the exported function name. It will be something like `ts_language_unreal_angelscript` or `tree_sitter_unreal_angelscript`. Match exactly.

**Warning signs:** `ImportError: DLL load failed` or `undefined symbol: tree_sitter_angelscript` at import time.

### Pitfall 2: tree-sitter-cli version mismatch when regenerating parser.c

**What goes wrong:** dimitrijejankov's `package.json` pins `tree-sitter-cli: ^0.20.0` but Node 24 / npx will fetch the latest (0.26+). The generated `parser.c` format changed between 0.20 and 0.25+.

**Why it happens:** `npx tree-sitter generate` without pinning fetches latest. The older `parser.c` in the repo was generated with 0.20.

**How to avoid:** If grammar.js is NOT modified, do NOT regenerate. Use the committed `src/parser.c` as-is. If grammar extension IS required, use `npx tree-sitter-cli@0.26 generate` (latest stable, compatible with tree-sitter Python 0.25.x). Do NOT use 0.20.

**Warning signs:** Compilation errors in `parser.c` citing undefined types, or `Language()` constructor failing with "incompatible language version" at runtime.

### Pitfall 3: Windows build without MSVC on PATH

**What goes wrong:** `uv sync` triggers `setup.py build_ext` but `cl.exe` is not on the default PATH in bash. setuptools falls back to trying MinGW which is also absent.

**Why it happens:** MSVC must be activated via `vcvarsall.bat` before build. In this project, the Python binary was compiled with MSC v.1944, so the matching MSVC toolchain must be used. `cl.exe` was confirmed not on PATH in the research environment.

**How to avoid:** Run `uv sync` from a Developer Command Prompt or Visual Studio terminal. Alternatively, document this as a setup step in the third-party package README. CI (Linux) has no issue — only local Windows dev.

**Warning signs:** `error: Microsoft Visual C++ 14.0 or greater is required` during `uv sync`.

**Mitigation:** The MSVC build tools ARE installed (Python was compiled with MSC v.1944), just not on the default bash PATH. Use `cmd.exe` with VS env activated for the initial `uv sync`. Subsequent runs work from any shell once the `.pyd` is cached.

### Pitfall 4: `#include` paths are not structured nodes

**What goes wrong:** Phase 4 expects to iterate child nodes of a `#include "file.as"` node to get the path. But dimitrijejankov treats all preprocessor directives as a catch-all token with no sub-nodes.

**Why it happens:** `preprocessor_directive: token(seq("#", /[^\r\n]*/))` — the whole line is a single terminal token, not a tree.

**How to avoid:** In Phase 4's AngelScript parser, extract the include path from `node.text.decode()` using a simple regex/string split on the preprocessor_directive text. This is fine — document it in coverage notes produced by this spike.

**Warning signs:** None at parse time. Fails silently in Phase 4 if code tries to access `node.children` on a preprocessor_directive node.

### Pitfall 5: `uv.lock` not updated after adding path dependency

**What goes wrong:** Adding the path dep to `pyproject.toml` but forgetting to run `uv sync` leaves `uv.lock` stale. CI will fail because the lockfile doesn't match.

**How to avoid:** Always run `uv sync` after modifying `pyproject.toml` and commit both `pyproject.toml` and `uv.lock` together.

---

## Code Examples

### Verify grammar function name before writing binding.c

```bash
# Run this after vendoring, before writing binding.c
head -5 third-party/tree-sitter-angelscript/src/parser.c
# Look for the exported function: TSLanguage *tree_sitter_unreal_angelscript(void)
```

### Minimal smoke test for the compiled binding

```python
# Source: verified pattern from existing parsers (python_lang.py line 21, csharp_lang.py line 27)
import tree_sitter_angelscript as tsas
from tree_sitter import Language, Parser

AS_LANGUAGE = Language(tsas.language())  # PyCapsule → Language object
parser = Parser(AS_LANGUAGE)

source = b"""
UCLASS(BlueprintType)
class AMyActor : AActor
{
    UFUNCTION(BlueprintCallable)
    void MyFunction()
    {
    }
}
"""

tree = parser.parse(source)
print(tree.root_node.sexp())  # Should print (program (class_declaration ...))
```

### pyproject.toml path dependency entry (exact syntax for uv)

```toml
# Add to [project.dependencies] in h:/Github/axon/pyproject.toml
# Position: after "tree-sitter-cpp>=0.23.0"
"tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript",
```

---

## Recommendation

**Use `dimitrijejankov/tree-sitter-unreal-angelscript` as the grammar source.**

Rationale: It is the only candidate with first-class UE5 macro support (UCLASS, UFUNCTION, UPROPERTY, USTRUCT, UENUM as structured AST nodes). Relrin covers generic AngelScript but has zero UE5 awareness and adds build complexity via an external scanner. The D-01 evaluation is complete — dimitrijejankov wins on all D-07 criteria except structured `#include` paths (catch-all preprocessor_directive, acceptable for Phase 4 with text extraction).

**Deliverable structure for this phase:**

1. Clone/copy dimitrijejankov into `third-party/tree-sitter-angelscript/`
2. Create `bindings/python/tree_sitter_angelscript/` scaffold (binding.c, `__init__.py`, `__init__.pyi`, `py.typed`)
3. Create `setup.py` and `pyproject.toml` in `third-party/tree-sitter-angelscript/`
4. Add path dep to `h:/Github/axon/pyproject.toml`
5. Run `uv sync` from Developer Command Prompt to build the `.pyd`
6. Write and run `tests/core/test_angelscript_binding.py` — must cover all four D-07 criteria
7. Commit `third-party/`, updated `pyproject.toml`, updated `uv.lock`, and test file

**Grammar extension trigger:** Only extend grammar.js if spike test fails on any D-07 criterion. Based on corpus tests reviewed, no extension should be needed — all D-07 criteria are met by the existing grammar.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| MSVC C++ tools | Building `_binding.pyd` on Windows | Partial | MSC v.1944 (not on bash PATH) | Use Developer Command Prompt for `uv sync` |
| Node.js | `npx tree-sitter generate` (if grammar.js extended) | Yes | 24.13.0 | Not needed if grammar.js unchanged |
| npm | `npx tree-sitter-cli@0.26` | Yes | 11.10.0 | — |
| tree-sitter CLI | Grammar generation | Not installed globally | — | Available via `npx tree-sitter-cli@0.26` |
| Python 3.11 | Build and runtime | Yes (in .venv) | 3.11 | — |
| uv | Dependency management | Yes | — | — |
| Git | Cloning grammar source | Yes | — | Download ZIP from GitHub |

**Missing dependencies with no fallback:**
- MSVC `cl.exe` not on bash PATH — `uv sync` must be run from a Visual Studio Developer Command Prompt or `cmd.exe` with `vcvarsall.bat x64` sourced.

**Missing dependencies with fallback:**
- tree-sitter CLI: available as `npx tree-sitter-cli@0.26 generate` — only needed if grammar.js is modified.

---

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_angelscript_binding.py -v` |
| Full suite command | `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| INFRA-06 | Binding importable; `language()` returns PyCapsule | unit | `pytest tests/core/test_angelscript_binding.py::test_binding_importable -v` | Wave 0 |
| INFRA-06 | Parse class with inheritance | unit | `pytest tests/core/test_angelscript_binding.py::test_parse_class_with_inheritance -v` | Wave 0 |
| INFRA-06 | Parse UFUNCTION macro | unit | `pytest tests/core/test_angelscript_binding.py::test_parse_ufunction -v` | Wave 0 |
| INFRA-06 | Parse import statement | unit | `pytest tests/core/test_angelscript_binding.py::test_parse_import -v` | Wave 0 |
| INFRA-06 | Parse preprocessor/include | unit | `pytest tests/core/test_angelscript_binding.py::test_parse_preprocessor_include -v` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/core/test_angelscript_binding.py -v`
- **Per wave merge:** Full suite (818 + new tests)
- **Phase gate:** `test_angelscript_binding.py` all green before Phase 4 can begin

### Wave 0 Gaps

- [ ] `tests/core/test_angelscript_binding.py` — covers all 5 INFRA-06 behaviors above (does not exist yet)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `Language.build_library()` in tree-sitter < 0.22 | Wheel-based `Language(pkg.language())` | tree-sitter 0.22+ | Cannot use build_library; must build proper C extension wheel |
| Single `setup.py` building all languages at once | One package per grammar | 0.22+ | Each grammar is its own installable package |

**Deprecated/outdated:**
- `Language.build_library(output_path, [grammar_dir])`: Removed in tree-sitter >= 0.22. Any tutorials showing this pattern are obsolete. Do not use.
- `tree-sitter-cli@0.20.0` (pinned in dimitrijejankov's package.json): Use `0.26+` if regeneration is needed. The older CLI is not compatible with tree-sitter Python 0.25.

---

## Open Questions

1. **Can `uv sync` compile C extensions on Windows without manual MSVC activation?**
   - What we know: Python was built with MSC v.1944; MSVC is installed; `cl.exe` not on bash PATH
   - What's unclear: Whether `uv` activates MSVC automatically via Python's distutils metadata
   - Recommendation: Test `uv sync` from bash; if it fails, document the Developer Command Prompt step in third-party package README and spike notes

2. **Does dimitrijejankov's pre-generated `src/parser.c` compile cleanly with MSVC 2022?**
   - What we know: `src/parser.c` exists and was generated with tree-sitter-cli 0.20
   - What's unclear: Whether 0.20-generated C code has any compatibility issues with MSVC 2022
   - Recommendation: Attempt compilation first; if it fails, regenerate with `npx tree-sitter-cli@0.26 generate`

---

## Sources

### Primary (HIGH confidence)

- GitHub API: `dimitrijejankov/tree-sitter-unreal-angelscript` — direct inspection of grammar.js (646 lines), corpus/ (14 test files), src/ directory listing
- GitHub API: `Relrin/tree-sitter-angelscript` — direct inspection of grammar.js (726 lines), src/ directory listing
- `/h/Github/axon/.venv/Lib/site-packages/tree_sitter_c_sharp/binding.c` — canonical binding pattern (local file, verified)
- `https://raw.githubusercontent.com/tree-sitter/tree-sitter-python/master/bindings/python/tree_sitter_python/binding.c` — canonical binding.c template
- `https://raw.githubusercontent.com/tree-sitter/tree-sitter-python/master/setup.py` — canonical setup.py template

### Secondary (MEDIUM confidence)

- Hazelight `language-server/pegjs/angelscript.pegjs` — partial grep verification of UCLASS/UFUNCTION/mixin/import patterns matching dimitrijejankov grammar

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**
- Grammar evaluation (dimitrijejankov vs Relrin): HIGH — directly fetched and analyzed grammar.js and corpus
- Python wheel scaffold pattern: HIGH — verified from installed packages and official tree-sitter-python source
- Windows build environment: MEDIUM — confirmed MSVC installed but `cl.exe` not on PATH; exact uv behavior untested
- Grammar coverage (D-07 criteria): HIGH for 3/4 criteria; MEDIUM for `#include` (confirmed catch-all, not blocking)

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (grammar repos are low-activity; stable for 30 days)
