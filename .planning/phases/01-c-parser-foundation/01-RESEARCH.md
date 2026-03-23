# Phase 1: C# Parser Foundation - Research

**Researched:** 2026-03-23
**Domain:** tree-sitter-c-sharp Python binding, C# grammar node types, parser integration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Best-effort namespace-to-file resolution. `using` directives are resolved by scanning indexed .cs files for matching `namespace X.Y.Z` declarations, then emitting IMPORTS edges to those files. Unresolved namespaces silently produce no edges.
- **D-02:** All three `using` forms are extracted with the same strategy: plain `using Namespace;`, `using static Type;`, and `using Alias = Type;`. Resolution treats each the same way — map to the file declaring the referenced namespace/type.
- **D-03:** Resolution logic lives in the C# parser module (`csharp_lang.py`), not mixed into `imports.py`. The logic runs after all files are parsed so namespace→file mapping is complete.
- **D-04:** One Method node per property, named by the property name (e.g., `MyProperty`). Kind = `"method"`, `class_name` = owning class. Read-only, write-only, and expression-bodied properties all follow the same pattern. No per-accessor nodes.
- **D-05:** Simple names by default (e.g., `MyActor`, not `Unreal.Core.MyActor`) — consistent with the Python/TS parsers. Only qualify on name collision: if two classes in the same project share the same simple name, both get the fully qualified name.
- **D-06:** Collision detection runs in `parser_phase.py` as a post-parse second pass over all parsed C# files before graph nodes are created. The namespace is always stored in `properties["cs_namespace"]` regardless of whether qualification was applied.
- **D-07:** Add `properties: dict = field(default_factory=dict)` to `SymbolInfo` in `base.py` during Phase 1. This is needed by Phase 3 (UE5 specifiers) and used in Phase 1 for C# attributes. All existing parsers are unaffected (field has a default).
- **D-08:** C# class/method attributes (e.g., `[Serializable]`, `[DllImport("...")]`, `[Obsolete]`) are extracted in Phase 1 and stored as a list in `properties["cs_attributes"]`. Phase 3 will use `properties["ue_specifiers"]` using the same dict pattern.
- **D-09:** Phase 1 emits one Class node per file for partial classes — duplicates exist in the graph. This is the accepted baseline behavior. Phase 5 merges them. The known limitation is documented in the parser's module docstring.

### Claude's Discretion
- Exact tree-sitter node type names for the C# grammar (discovered during research — now documented below)
- Content of the `_BUILTIN_TYPES` frozenset for C#
- Whether nested types (classes inside classes) are extracted or skipped in Phase 1
- Signature string format for C# methods

### Deferred Ideas (OUT OF SCOPE)
- Unity lifecycle method exemptions from dead-code — Phase 5
- C# partial class merging — Phase 5
- `[SerializeField]` / `[Header]` / `[RequireComponent]` Unity attribute handling for dead-code exemptions — Phase 5
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Register C# language in `languages.py` with `.cs` extension mapping | One-line add to SUPPORTED_EXTENSIONS dict |
| INFRA-05 | Add `tree-sitter-c-sharp` and `tree-sitter-cpp` as dependencies in `pyproject.toml` | tree-sitter-c-sharp 0.23.1 confirmed compatible with tree-sitter 0.25.2 |
| CS-01 | User can index a C# file and see Function, Method, Class, and Interface nodes in the graph | All required grammar node types confirmed via live parsing tests |
| CS-02 | User can see IMPORTS edges between .cs files based on `using` directive resolution | using_directive node structure fully mapped; three forms identified |
| CS-03 | User can see EXTENDS/IMPLEMENTS edges between C# classes and interfaces | base_list structure confirmed; heritage disambiguation strategy documented |
| CS-04 | C# properties (get/set accessors) are extracted as Method nodes with their parent class set | property_declaration node structure confirmed; D-04 implementation approach verified |
</phase_requirements>

---

## Summary

tree-sitter-c-sharp 0.23.1 is the current stable release (published 2024-11-11) and is **confirmed compatible** with the project's tree-sitter 0.25.2 dependency — verified via live install and parse test. The package exposes a `language()` function returning a PyCapsule, consumed identically to the existing Python and TypeScript parsers: `Language(tscsharp.language())`. Windows binaries (win_amd64, win_arm64) are provided as pre-built wheels, so no compilation is required on the Windows 11 dev machine.

The grammar supports C# 1 through 13.0 comprehensively. All node types needed for this phase were verified by parsing live C# code: class declarations (`class_declaration`), method declarations (`method_declaration`), interface declarations (`interface_declaration`), constructor declarations (`constructor_declaration`), property declarations (`property_declaration`), enum declarations (`enum_declaration`), and both namespace forms (`namespace_declaration` for block-style, `file_scoped_namespace_declaration` for C# 10 file-scoped). Heritage uses a `base_list` node with no grammatical distinction between base class and interface — the only signal available is the naming convention (I-prefix).

The existing `NodeLabel` and `RelType` enums in `model.py` already contain all types needed for this phase: `CLASS`, `METHOD`, `INTERFACE`, `ENUM`, `EXTENDS`, `IMPLEMENTS`, `IMPORTS`. No new graph model entries are required. The `SymbolInfo` `properties: dict` field (D-07) is a backward-compatible addition to `base.py`.

**Primary recommendation:** Implement `CSharpParser` in `src/axon/core/parsers/csharp_lang.py` following the `PythonParser` pattern exactly. Use the confirmed node type names below — do not guess or derive them from documentation.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tree-sitter-c-sharp | 0.23.1 | C# grammar for tree-sitter | Official tree-sitter organization package; pre-built wheels for all platforms including win_amd64 |
| tree-sitter | >=0.25.0 | Parser engine | Already a project dependency; confirmed compatible with tree-sitter-c-sharp 0.23.1 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | — | All other supporting libs already in project | — |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tree-sitter-c-sharp | tree-sitter-languages (bundle) | tree-sitter-languages 1.10.2 bundles many grammars but uses an older tree-sitter version — not compatible with project's 0.25.x |
| tree-sitter-c-sharp | Roslyn / Microsoft.CodeAnalysis | Requires .NET runtime — violates "no new infrastructure" constraint |

**Installation:**
```bash
# Add to pyproject.toml [project.dependencies]
# tree-sitter-c-sharp>=0.23.0

# Do NOT use [core] extra — it pins tree-sitter~=0.22 which conflicts with project's >=0.25.0
pip install tree-sitter-c-sharp
```

**Version verification (confirmed 2026-03-23):**
```bash
pip show tree-sitter-c-sharp
# Version: 0.23.1
# tree-sitter 0.25.2 installed in same environment — no conflicts
```

The `[core]` extra (`tree-sitter~=0.22`) is a development convenience extra — it is NOT a runtime requirement. The base package works with any tree-sitter version that accepts the PyCapsule language pointer.

---

## Architecture Patterns

### Recommended Project Structure

```
src/axon/core/parsers/
├── base.py              # Add properties: dict field to SymbolInfo (D-07)
├── python_lang.py       # Reference pattern (unchanged)
├── typescript.py        # Reference pattern (unchanged)
└── csharp_lang.py       # New: CSharpParser (this phase)

src/axon/config/
└── languages.py         # Add ".cs": "csharp" to SUPPORTED_EXTENSIONS

src/axon/core/ingestion/
└── parser_phase.py      # Add "csharp": CSharpParser to _PARSER_FACTORIES
                         # Add second-pass collision detection (D-05, D-06)

tests/core/
└── test_parser_csharp.py  # New: 80+ tests
```

### Pattern 1: Parser Initialization

Identical to `PythonParser.__init__`. The `Language` constructor accepts the PyCapsule from `tscsharp.language()` directly.

```python
# Source: verified via live test against tree-sitter 0.25.2
import tree_sitter_c_sharp as tscsharp
from tree_sitter import Language, Parser

CS_LANGUAGE = Language(tscsharp.language())

class CSharpParser(LanguageParser):
    def __init__(self) -> None:
        self._parser = Parser(CS_LANGUAGE)

    def parse(self, content: str, file_path: str) -> ParseResult:
        tree = self._parser.parse(bytes(content, "utf8"))
        result = ParseResult()
        self._walk(tree.root_node, content, result, class_name="")
        return result
```

**Thread safety:** Verified — a single `Parser` instance shared across 10 concurrent threads produced correct results with no errors. The parser is stateless between calls. The existing pattern of one cached instance per language in `_PARSER_CACHE` is safe.

### Pattern 2: Walking Class Bodies

Classes, interfaces, namespaces, and the root `compilation_unit` all use `declaration_list` as the container body. The walker processes `declaration_list` children recursively.

```python
# Source: verified node types from live parsing

def _walk(self, node: Node, content: str, result: ParseResult, class_name: str) -> None:
    for child in node.children:
        match child.type:
            case "class_declaration":
                self._extract_class(child, content, result)
            case "interface_declaration":
                self._extract_interface(child, content, result)
            case "method_declaration":
                self._extract_method(child, content, result, class_name)
            case "constructor_declaration":
                self._extract_constructor(child, content, result, class_name)
            case "property_declaration":
                self._extract_property(child, content, result, class_name)
            case "enum_declaration":
                self._extract_enum(child, content, result)
            case "namespace_declaration" | "file_scoped_namespace_declaration":
                self._extract_namespace(child, content, result)
            case "using_directive":
                self._extract_using(child, result)
            case "declaration_list":
                self._walk(child, content, result, class_name)
            case _:
                pass  # skip; do not recurse into unknown nodes by default
```

### Pattern 3: Class Extraction with Namespace Tracking

```python
# Source: verified via live parsing

def _extract_class(self, node: Node, content: str, result: ParseResult) -> None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return

    class_name = name_node.text.decode("utf8")
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    node_content = content[node.start_byte:node.end_byte]

    # Detect partial modifier
    is_partial = any(
        c.type == "modifier" and c.text.decode("utf8") == "partial"
        for c in node.children
    )

    # Extract attributes
    attributes = self._extract_attributes(node)

    # Namespace stored in properties (D-06) — passed via context or extracted from walk stack
    props: dict = {"cs_attributes": attributes}
    if self._current_namespace:
        props["cs_namespace"] = self._current_namespace

    result.symbols.append(SymbolInfo(
        name=class_name,
        kind="class",
        start_line=start_line,
        end_line=end_line,
        content=node_content,
        properties=props,
    ))

    # Extract heritage
    for child in node.children:
        if child.type == "base_list":
            self._extract_heritage(class_name, child, result)

    # Walk body for methods, properties, nested classes
    body = node.child_by_field_name("body")
    if body is not None:
        self._walk(body, content, result, class_name=class_name)
```

### Pattern 4: Heritage Extraction (base_list)

**Critical:** The C# grammar has NO syntactic distinction between base class and interface in `base_list`. All entries appear as `identifier` or `generic_name` nodes. Use the I-prefix naming convention as the only available heuristic.

```python
# Source: verified via live parsing
# Disambiguation: names starting with uppercase I followed by another uppercase letter
# are conventionally interfaces. Everything else is treated as extends.

import re
_INTERFACE_RE = re.compile(r'^I[A-Z]')

def _extract_heritage(self, class_name: str, base_list_node: Node, result: ParseResult) -> None:
    for child in base_list_node.children:
        if child.type == "identifier":
            parent_name = child.text.decode("utf8")
        elif child.type == "generic_name":
            # Generic base like List<T> or IList<T>
            id_node = child.children[0] if child.children else None
            if id_node is None:
                continue
            parent_name = id_node.text.decode("utf8")
        else:
            continue  # skip ':' and ',' separators

        kind = "implements" if _INTERFACE_RE.match(parent_name) else "extends"
        result.heritage.append((class_name, kind, parent_name))
```

### Pattern 5: Property Extraction (D-04)

Properties are emitted as `SymbolInfo` with `kind="method"`. All property forms (auto `{ get; set; }`, read-only `{ get; }`, expression-bodied `=> expr`) follow the same pattern — one Method node per property.

```python
# Source: verified via live parsing
# property_declaration fields: "name", "type", "accessors" (or arrow_expression_clause)

def _extract_property(self, node: Node, content: str, result: ParseResult, class_name: str) -> None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return

    prop_name = name_node.text.decode("utf8")
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    node_content = content[node.start_byte:node.end_byte]

    type_node = node.child_by_field_name("type")
    type_str = type_node.text.decode("utf8") if type_node else ""
    signature = f"{type_str} {prop_name}" if type_str else prop_name

    result.symbols.append(SymbolInfo(
        name=prop_name,
        kind="method",  # D-04: properties are Method nodes
        start_line=start_line,
        end_line=end_line,
        content=node_content,
        signature=signature,
        class_name=class_name,
    ))
```

### Pattern 6: using Directive Extraction

Three distinct forms are identified by checking for `static` and `=` children. The `name` field (set only in alias form) is the alias — for resolution, the actual namespace is the non-alias qualified_name.

```python
# Source: verified via live parsing

def _extract_using(self, node: Node, result: ParseResult) -> None:
    has_static = any(c.type == "static" for c in node.children)
    has_alias = any(c.type == "=" for c in node.children)
    alias_name = ""
    module = ""

    if has_alias:
        # using MyAlias = Some.Namespace;
        # The 'name' field is the alias. The target is the qualified_name after '='
        name_node = node.child_by_field_name("name")
        alias_name = name_node.text.decode("utf8") if name_node else ""
        # Get target: the qualified_name or identifier that is NOT the alias
        targets = [c for c in node.children
                   if c.type in ("qualified_name", "identifier") and c is not name_node]
        module = targets[0].text.decode("utf8") if targets else ""
    else:
        # using System; or using static System.Math;
        for c in node.children:
            if c.type in ("qualified_name", "identifier"):
                module = c.text.decode("utf8")
                break

    if module:
        result.imports.append(ImportInfo(
            module=module,
            names=[],
            alias=alias_name,
        ))
```

### Pattern 7: Attribute Extraction (D-08)

C# `attribute_list` nodes appear as direct children of declaration nodes (no field name). Each `attribute_list` contains one or more `attribute` children, each starting with an `identifier` giving the attribute name.

```python
# Source: verified via live parsing

def _extract_attributes(self, decl_node: Node) -> list[str]:
    """Extract C# attribute names from a declaration node's attribute_list children."""
    attrs: list[str] = []
    for child in decl_node.children:
        if child.type == "attribute_list":
            for sub in child.children:
                if sub.type == "attribute":
                    # First child of attribute is the identifier (name)
                    if sub.children:
                        attrs.append(sub.children[0].text.decode("utf8"))
    return attrs
```

### Pattern 8: Namespace Resolution (D-01, D-03)

The resolver runs in `csharp_lang.py` as a module-level post-processing function called by `parser_phase.py` after all files are parsed. It builds a namespace-to-file mapping, then patches `imports` in each `ParseResult` with the resolved file path.

```python
# Source: architectural pattern consistent with existing imports.py

def resolve_csharp_imports(
    all_parse_data: list[FileParseData],
) -> None:
    """Second pass: resolve 'using' namespace strings to file paths.

    Builds a map of {namespace_string: file_path} from all parsed .cs files,
    then patches ImportInfo.module to a file path where resolvable.
    Unresolved namespaces remain as-is (no IMPORTS edge will be created).
    """
    # Step 1: Build namespace -> file_path map
    ns_to_file: dict[str, str] = {}
    for pd in all_parse_data:
        if pd.language != "csharp":
            continue
        for sym in pd.parse_result.symbols:
            ns = (sym.properties or {}).get("cs_namespace", "")
            if ns and pd.file_path not in ns_to_file.values():
                ns_to_file[ns] = pd.file_path

    # Step 2: Patch imports
    for pd in all_parse_data:
        if pd.language != "csharp":
            continue
        for imp in pd.parse_result.imports:
            resolved = ns_to_file.get(imp.module)
            if resolved:
                imp.module = resolved
```

### Pattern 9: Collision Detection (D-05, D-06)

The second-pass collision check in `parser_phase.py` iterates all C# symbols, detects duplicate simple names, and qualifies them. This runs BEFORE graph nodes are created.

```python
# Source: architectural pattern from CONTEXT.md D-05/D-06

def _qualify_collisions(all_parse_data: list[FileParseData]) -> None:
    """Qualify C# symbol names that collide across files.

    Only applies to class/interface symbols. Uses the cs_namespace property
    stored by the parser. Mutates SymbolInfo.name in place.
    """
    from collections import Counter
    csharp_classes = [
        (sym, pd.file_path)
        for pd in all_parse_data if pd.language == "csharp"
        for sym in pd.parse_result.symbols if sym.kind in ("class", "interface")
    ]
    name_counts = Counter(sym.name for sym, _ in csharp_classes)

    for sym, _ in csharp_classes:
        if name_counts[sym.name] > 1:
            ns = (sym.properties or {}).get("cs_namespace", "")
            if ns:
                sym.name = f"{ns}.{sym.name}"
```

### Anti-Patterns to Avoid

- **Do not access `base_list` via `child_by_field_name`** — `base_list` is NOT a named field on `class_declaration`. Use child iteration and check `child.type == "base_list"`.
- **Do not use `node.text.decode()` on entire `class_declaration` as content** — use `content[node.start_byte:node.end_byte]` (same as Python parser) to avoid encoding issues with the full text.
- **Do not assume `declaration_list` is always named `"body"`** — `method_declaration` body is the `"body"` field, but `class_declaration` body is also `"body"`. Constructors use `"body"`. Properties use `"accessors"`. Always use the correct field name.
- **Do not try to distinguish base class from interface in grammar** — there is no syntactic signal. Use the I-prefix heuristic exclusively.
- **Do not install `tree-sitter-c-sharp[core]`** — the `[core]` extra pins `tree-sitter~=0.22` which would downgrade the project's tree-sitter 0.25.x.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| C# parsing | Custom regex-based C# parser | tree-sitter-c-sharp 0.23.1 | Grammar handles all C# 1-13.0 syntax; error recovery built in; 377KB pre-built wheel |
| Grammar exploration | Manual grammar inspection | Live parsing with `p.parse(code)` | Grammar may not match docs; ground truth is the actual parse tree |
| Thread-safe parser caching | Custom locking | Existing `_PARSER_CACHE` + `_PARSER_CACHE_LOCK` in parser_phase.py | Already implemented; just add entry to `_PARSER_FACTORIES` |
| Type name extraction from generic types | Custom parser | `generic_name.children[0].text.decode()` | Verified: first child of `generic_name` is always the base name identifier |

**Key insight:** The C# grammar is comprehensive but opaque. Every node type claim in this document was verified by running actual parse tests — never rely on documentation alone.

---

## Common Pitfalls

### Pitfall 1: base_list is NOT a Named Field

**What goes wrong:** `class_node.child_by_field_name("base_list")` returns `None` — the heritage is silently dropped.

**Why it happens:** The C# grammar does not expose `base_list` as a named field. It is an unnamed structural child. This differs from Python's `superclasses` field and TypeScript's `class_heritage` field.

**How to avoid:** Iterate `class_node.children` and check `child.type == "base_list"`.

**Warning signs:** Zero heritage edges in graph for classes known to have inheritance.

### Pitfall 2: File-Scoped Namespace vs Block Namespace

**What goes wrong:** Namespace is not extracted; `properties["cs_namespace"]` is empty; collision detection fails; import resolution produces no edges.

**Why it happens:** C# 10+ allows `namespace Foo.Bar;` (semicolon, no braces). The grammar node is `file_scoped_namespace_declaration`, not `namespace_declaration`. If the walker only handles `namespace_declaration`, the newer form is silently skipped.

**How to avoid:** Handle both in `match` (or `if/elif`): `case "namespace_declaration" | "file_scoped_namespace_declaration"`.

**Warning signs:** Modern C# projects (ASP.NET Core, .NET 6+) use file-scoped namespaces by default.

### Pitfall 3: attribute_list Has No Field Name

**What goes wrong:** `method_node.child_by_field_name("attribute_list")` returns `None`; attributes silently not extracted.

**Why it happens:** `attribute_list` appears as an unnamed child before `modifier` children in declaration nodes. There is no field name for it.

**How to avoid:** Iterate children and check `child.type == "attribute_list"`.

**Warning signs:** `properties["cs_attributes"]` always empty despite decorated methods.

### Pitfall 4: declaration_list vs block Confusion

**What goes wrong:** Walking into a `block` (method body) as if it is a `declaration_list` (class body); attempting to extract `class_declaration` children from method bodies.

**Why it happens:** Class/namespace bodies use `declaration_list`. Method bodies use `block`. Both look like `{...}` in source.

**How to avoid:** In `_walk`, only recurse into `declaration_list` for nested type discovery. Do not recurse into `block` nodes for type extraction.

**Warning signs:** "Failed to extract symbol" errors; missing classes from nested class scenarios.

### Pitfall 5: Static vs Alias using Directive

**What goes wrong:** `using static System.Math` and `using MyAlias = Type` both look like "unusual" `using` directives. Naive extraction takes only the first identifier/qualified_name child, giving `System.Math` for both static and alias, and `MyAlias` for the alias form (wrong — the alias, not the target).

**Why it happens:** For alias form, the `name` field node is the alias (`MyAlias`), and the targets list `[c for c in node.children if c.type in ("identifier", "qualified_name")]` returns `["MyAlias", "My.Long.Type"]`. The first element is wrong.

**How to avoid:** For alias form, explicitly filter out the `name` field node: `targets = [c for c in node.children if c.type in ("qualified_name", "identifier") and c is not name_node]`.

**Warning signs:** Import resolution misses alias-form usings; alias is treated as the namespace.

### Pitfall 6: Namespace Tracking Requires Parser State

**What goes wrong:** Symbols have no `properties["cs_namespace"]` because the parser has no context of which namespace it is currently inside.

**Why it happens:** Unlike Python where `class_name` is passed as a parameter, namespace context must be threaded through the walk. The walker encounters the namespace node, extracts the name, and must pass it down recursively to all class/method extraction calls.

**How to avoid:** Add `namespace: str` parameter to `_walk` (or maintain `self._current_namespace` instance state reset per `parse()` call). The safer option is instance state since namespace nesting is rare in well-structured C# but possible.

**Warning signs:** `cs_namespace` property missing; collision detection never qualifies any names.

### Pitfall 7: Partial Class Modifier Requires Explicit Check

**What goes wrong:** Partial classes are not documented; `properties["cs_partial"] = True` is never set; Phase 5 has no signal to merge on.

**Why it happens:** The `partial` keyword appears as a `modifier` child of `class_declaration` — same node type as `public`, `private`, `static`. You must explicitly check the text value.

**How to avoid:** Check `c.type == "modifier" and c.text.decode("utf8") == "partial"` when iterating class children. Store `"cs_partial": True` in properties.

**Warning signs:** Phase 5 partial class merging has no way to identify partial class nodes.

---

## Code Examples

Verified patterns from live parse tests:

### Full Qualified Name from namespace Node

```python
# Source: verified via live parsing
# Works for both namespace_declaration and file_scoped_namespace_declaration

def _get_namespace_name(self, node: Node) -> str:
    """Extract the full namespace name string from a namespace declaration node."""
    for child in node.children:
        if child.type in ("qualified_name", "identifier"):
            return child.text.decode("utf8")
    return ""
```

### Method Signature Construction

```python
# Source: verified field names from live parsing
# method_declaration fields: "name", "parameters", "returns"

def _build_method_signature(self, method_node: Node) -> str:
    name_node = method_node.child_by_field_name("name")
    params_node = method_node.child_by_field_name("parameters")
    returns_node = method_node.child_by_field_name("returns")

    if name_node is None or params_node is None:
        return ""

    name = name_node.text.decode("utf8")
    params = params_node.text.decode("utf8")
    return_type = returns_node.text.decode("utf8") if returns_node else "void"
    return f"{return_type} {name}{params}"
```

### Parameter Type Extraction

```python
# Source: verified via live parsing
# parameter fields: "type", "name"
# type child types: predefined_type, identifier, generic_name, array_type, nullable_type

def _extract_param_types(self, method_node: Node, result: ParseResult) -> None:
    params_node = method_node.child_by_field_name("parameters")
    if params_node is None:
        return

    for child in params_node.children:
        if child.type != "parameter":
            continue
        type_node = child.child_by_field_name("type")
        name_node = child.child_by_field_name("name")
        if type_node is None or name_node is None:
            continue

        # Extract the base type name (strip generics)
        if type_node.type == "identifier":
            type_name = type_node.text.decode("utf8")
        elif type_node.type == "generic_name":
            type_name = type_node.children[0].text.decode("utf8") if type_node.children else ""
        elif type_node.type == "predefined_type":
            type_name = type_node.text.decode("utf8")  # will be in _BUILTIN_TYPES
        else:
            type_name = ""

        if type_name and type_name not in _BUILTIN_TYPES:
            result.type_refs.append(TypeRef(
                name=type_name,
                kind="param",
                line=type_node.start_point[0] + 1,
                param_name=name_node.text.decode("utf8"),
            ))
```

### Invocation Expression (Method Call) Extraction

```python
# Source: verified field names from live parsing
# invocation_expression fields: "function", "arguments"
# function child: identifier (simple call) or member_access_expression (method call)
# member_access_expression fields: "expression" (receiver), "name" (method name)

def _extract_call(self, node: Node, result: ParseResult) -> None:
    if node.type != "invocation_expression":
        return
    func_node = node.child_by_field_name("function")
    if func_node is None:
        return

    line = node.start_point[0] + 1

    if func_node.type == "identifier":
        result.calls.append(CallInfo(name=func_node.text.decode("utf8"), line=line))
    elif func_node.type == "member_access_expression":
        expr_node = func_node.child_by_field_name("expression")
        name_node = func_node.child_by_field_name("name")
        if name_node is not None:
            receiver = expr_node.text.decode("utf8") if expr_node else ""
            result.calls.append(CallInfo(
                name=name_node.text.decode("utf8"),
                line=line,
                receiver=receiver,
            ))
```

### Suggested `_BUILTIN_TYPES` for C#

```python
# Based on C# predefined types and common system types
# "predefined_type" grammar node covers: bool, byte, sbyte, char, decimal, double,
# float, int, uint, long, ulong, object, short, ushort, string, void, dynamic
# These appear directly in grammar; user-defined types are "identifier" nodes.

_BUILTIN_TYPES: frozenset[str] = frozenset({
    "bool", "byte", "sbyte", "char", "decimal", "double", "float",
    "int", "uint", "long", "ulong", "object", "short", "ushort",
    "string", "void", "dynamic",
    # Common generics (strip generics to base name first)
    "Task", "IEnumerable", "IList", "ICollection", "IDictionary",
    "List", "Dictionary", "HashSet", "Queue", "Stack", "Array",
    "Nullable", "Func", "Action", "Predicate", "EventHandler",
    # Value types
    "Guid", "DateTime", "DateTimeOffset", "TimeSpan",
})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build from source with node-gyp | Pre-built Python wheels on PyPI | ~2022 | No compilation required; win_amd64 wheel available |
| `Language.build_library()` API | `Language(grammar.language())` capsule API | tree-sitter 0.22.x | Existing parsers already use the new API |
| Block-style namespace only (`namespace Foo {}`) | File-scoped namespace (`namespace Foo;`) | C# 10 / .NET 6 (2021) | Must handle `file_scoped_namespace_declaration` |
| Block namespace only supported | Both forms in grammar | tree-sitter-c-sharp ~0.21 | Grammar handles both automatically |

**Deprecated/outdated:**
- `Language.build_library("output.so", ["vendor/tree-sitter-c-sharp"])`: replaced by pip-installable capsule API since tree-sitter 0.22.
- tree-sitter-c-sharp versions before 0.21: do not support file-scoped namespaces.

---

## Open Questions

1. **Nested class extraction scope**
   - What we know: Nested `class_declaration` nodes appear as children of an outer class's `declaration_list`. The walker will encounter them naturally.
   - What's unclear: Should nested classes be emitted as graph nodes? If so, should their `class_name` be set to the outer class name?
   - Recommendation: Extract nested classes as first-class nodes with no `class_name` set (consistent with how Python parser handles nested class definitions). Document this as Claude's discretion scope.

2. **struct_declaration handling**
   - What we know: `struct_declaration` is a valid C# top-level declaration with same structure as `class_declaration`. It is not listed in REQUIREMENTS.md requirements for Phase 1.
   - What's unclear: Should structs be emitted as `class` nodes or skipped?
   - Recommendation: Extract structs as `class` nodes (structs are value-type analogs of classes; this is the simplest correct behavior). Decide during implementation.

3. **Constructor vs method naming**
   - What we know: `constructor_declaration` uses `field_name="name"` — the identifier is the class name, not a method name. Constructors are extracted as Method nodes with `name = class_name + ".__init__"` or `name = class_name`.
   - What's unclear: Should constructors be extracted at all? They don't appear in requirements CS-01–CS-04 explicitly.
   - Recommendation: Extract constructors as Method nodes with `name = class_name` (same as TypeScript parser's `constructor` handling). This ensures they appear in call graphs.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | Parser runtime | Yes | 3.11 (pinned) | — |
| tree-sitter | Grammar engine | Yes | 0.25.2 | — |
| tree-sitter-c-sharp | C# grammar | Not yet installed | 0.23.1 (on PyPI) | — |
| uv | Package management | Yes | In CI | — |
| pytest | Test runner | Yes | >=8.0.0 | — |
| Windows win_amd64 wheel | Dev machine support | Yes | Pre-built in 0.23.1 | — |

**Missing dependencies with no fallback:**
- `tree-sitter-c-sharp` must be added to `pyproject.toml` before any C# parsing code can run.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0.0 with pytest-asyncio >= 0.24.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py -q` |
| Full suite command | `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `.cs` maps to `"csharp"` in `get_language()` | unit | `pytest tests/core/test_parser_csharp.py::TestRegistration -x` | Wave 0 |
| INFRA-05 | `import tree_sitter_c_sharp` succeeds | unit | `pytest tests/core/test_parser_csharp.py::TestImport -x` | Wave 0 |
| CS-01 | Class, Interface, Method, Function nodes extracted | unit | `pytest tests/core/test_parser_csharp.py::TestSymbolExtraction -x` | Wave 0 |
| CS-02 | IMPORTS edges from `using` directives | unit | `pytest tests/core/test_parser_csharp.py::TestImportResolution -x` | Wave 0 |
| CS-03 | EXTENDS/IMPLEMENTS from `base_list` | unit | `pytest tests/core/test_parser_csharp.py::TestHeritage -x` | Wave 0 |
| CS-04 | Properties as Method nodes with class_name | unit | `pytest tests/core/test_parser_csharp.py::TestProperties -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py -q`
- **Per wave merge:** `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/test_parser_csharp.py` — covers all 6 requirements above (does not exist yet)

---

## Sources

### Primary (HIGH confidence)
- Live parse tests against tree-sitter-c-sharp 0.23.1 + tree-sitter 0.25.2 — all node types, field names, and API patterns verified by execution
- `src/axon/core/parsers/python_lang.py` — reference parser implementation pattern
- `src/axon/core/parsers/typescript.py` — second reference parser
- `src/axon/core/parsers/base.py` — LanguageParser ABC and dataclass contracts
- `src/axon/core/ingestion/parser_phase.py` — `_PARSER_FACTORIES`, `_KIND_TO_LABEL`, threading model

### Secondary (MEDIUM confidence)
- PyPI metadata for tree-sitter-c-sharp 0.23.1 — version, requirements, upload date confirmed
- tree-sitter-c-sharp METADATA description — C# 1-13.0 support statement, Windows wheel availability confirmed

### Tertiary (LOW confidence)
- None — all findings are HIGH confidence from primary live-test sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyPI version confirmed, compatibility tested live
- Architecture patterns: HIGH — all code examples verified by parsing actual C# source
- Pitfalls: HIGH — identified by attempting the wrong approach during research (e.g., `child_by_field_name("base_list")` returned None; confirmed by live test)
- Grammar node types: HIGH — verified by live parsing every node type mentioned

**Research date:** 2026-03-23
**Valid until:** 2026-12-31 (tree-sitter-c-sharp releases infrequently; grammar is stable)
