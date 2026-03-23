# Architecture Patterns: Language Parser Extensions (C#, UE5 C++, AngelScript)

**Project:** Axon Language Extension: C#, UE5 C++, AngelScript
**Researched:** 2026-03-23
**Confidence:** MEDIUM-HIGH (tree-sitter grammars verified; UE5 macro semantics from training/memory; AngelScript syntax via general research)

---

## Executive Summary

Adding three new language parsers (C#, UE5 C++, AngelScript) to Axon requires minimal architectural changes because the parser abstraction (`LanguageParser` protocol) is language-agnostic. All parsers must emit the same `ParseResult` dataclass, allowing downstream phases (calls, heritage, types, community, dead_code) to operate unchanged.

**Key architectural decisions:**

1. **No new NodeLabel enum entries required** — Use existing FUNCTION, CLASS, METHOD, INTERFACE, ENUM labels plus `properties` dict for UE5 metadata (UCLASS, UFUNCTION, UPROPERTY, Blueprint flags).
2. **MODULE as a future enhancement** — .Build.cs files can be integrated as part of the C++ parser for now; defer MODULE node type to a separate phase if modular analysis becomes critical.
3. **Language-specific base classes optional** — All three parsers can be fully independent; shared UE5 base utilities (macro pattern matching, exemption registry) go in dead_code.py and a new `ue5_utils.py` module.
4. **Dead-code exemption strategy** — Extend dead_code.py with UE5 Blueprint-exposure detection and Unity lifecycle hooks; do NOT require schema changes.
5. **Build order:** C# first (lowest complexity, no UE5 macro complexity), then UE5 C++, then AngelScript (most dependent on UE5 awareness established in dead_code).

---

## Recommended Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ingestion Pipeline                         │
│  (walker → structure → parser_phase → imports → ... → coupling) │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │    parser_phase.py                 │
        │  _PARSER_FACTORIES dict            │
        │  get_parser(language) → instance   │
        └────────┬───────────────────────────┘
                 │
        ┌────────┴──────────────────────────┐
        │                                   │
        ▼                                   ▼
  ┌──────────────────────┐         ┌──────────────────────┐
  │  Language Parsers    │         │ Configuration        │
  │  (tree-sitter)       │         │ languages.py         │
  │                      │         │ extension → language │
  │  • PythonParser      │         │ mapping              │
  │  • TypeScriptParser  │         │                      │
  │  • CSharpParser      │         │ (.cs → "csharp")     │
  │  • CppUE5Parser      │         │ (.h/.cpp → "cpp_ue5")
  │  • AngelScriptParser │         │ (.as → "angelscript") │
  └──────────┬───────────┘         └──────────────────────┘
             │
             ▼
      ┌─────────────────────────────────────────┐
      │      ParseResult (language-agnostic)    │
      │  • symbols: [SymbolInfo]                │
      │  • imports: [ImportInfo]                │
      │  • calls: [CallInfo]                    │
      │  • heritage: [(name, kind, parent)]     │
      │  • type_refs: [TypeRef]                 │
      │  • exports: [names]                     │
      └────────────┬────────────────────────────┘
                   │
      ┌────────────┴────────────┐
      │                         │
      ▼                         ▼
  ┌──────────────────┐   ┌────────────────────────┐
  │  parser_phase.py │   │  Dead-Code Exemptions │
  │  process_parsing │   │  dead_code.py         │
  │  • Create nodes  │   │ (extended for UE5)    │
  │  • DEFINES edges │   │ • UE5 Blueprint check │
  │  • Store parse   │   │ • Unity lifecycle     │
  │    data for      │   │ • AngelScript UE-annot
  │    later phases  │   └────────────────────────┘
  └──────────────────┘
```

### Parser Implementation Pattern

Each parser is a concrete `LanguageParser` implementation:

```python
from axon.core.parsers.base import LanguageParser, ParseResult, SymbolInfo, ImportInfo, CallInfo, TypeRef

class CSharpParser(LanguageParser):
    def __init__(self):
        self._language = Language(tree_sitter_c_sharp.language())
        self._parser = Parser(self._language)

    def parse(self, content: str, file_path: str) -> ParseResult:
        tree = self._parser.parse(content.encode("utf-8"))
        result = ParseResult()
        # Extract symbols, imports, calls, heritage, type_refs, exports
        # Store C# attributes ([SerializeField], etc.) in properties dict
        return result
```

**Key pattern from existing parsers (typescript.py, python_lang.py):**
- Walk tree-sitter AST recursively, dispatching on `node.type`
- Accumulate results in `ParseResult` fields
- For symbols with metadata (decorators, attributes, base classes), store in `SymbolInfo.properties` or via `ParseData` dataclass
- Let downstream phases consume raw metadata via graph node `properties` dict

---

## Component Boundaries

### Parser Components

| Component | Responsibility | Integration Point |
|-----------|---------------|-------------------|
| **CSharpParser** | Parse .cs files; extract classes, methods, interfaces, properties, enums; capture C# attributes ([SerializeField], [Header], etc.) as `properties["attributes"]` | `parser_phase.py:_PARSER_FACTORIES` |
| **CppUE5Parser** | Parse .h and .cpp files; extract classes, methods, functions; capture UE5 macros (UCLASS, UFUNCTION, UPROPERTY, Blueprint flags) as `properties["ue5_macros"]` | `parser_phase.py:_PARSER_FACTORIES` |
| **AngelScriptParser** | Parse .as files; extract classes, methods, functions; capture UE5-style annotations as `properties["ue5_annotations"]` | `parser_phase.py:_PARSER_FACTORIES` |
| **ue5_utils.py** (new) | Shared utilities: UE5 macro regex patterns, Blueprint exposure detection, UE5 base class registry (AActor, UObject, ACharacter, etc.) | `dead_code.py`, all UE5 parsers |

### Configuration Changes

| File | Change | Impact |
|------|--------|--------|
| `languages.py` | Add mappings: `.cs → "csharp"`, `.h/.cpp → "cpp_ue5"`, `.as → "angelscript"`, `.Build.cs → "cpp_ue5_build"` | File discovery in walker.py; determines which parser is invoked |
| `parser_phase.py:_PARSER_FACTORIES` | Add factory functions for three new parsers | Enables lazy parser instantiation and caching |

### Dead-Code Exemption Extensions

| Module | Change | Scope |
|--------|--------|-------|
| `dead_code.py` | Add `_is_ue5_blueprint_exposed(node)` predicate | Exempt Blueprint-callable/event/nativeevent functions |
| `dead_code.py` | Add `_is_unity_lifecycle_method(name, class_name)` predicate | Exempt MonoBehaviour lifecycle methods (Start, Update, OnEnable, etc.) |
| `ue5_utils.py` (new) | `UE5_BASE_CLASSES` registry, `is_ue5_base_class()`, `parse_uclass_macro()` | Centralize UE5-specific knowledge; support dead_code.py checks |

---

## Data Flow: Parser → Graph Node

### Example 1: C# Attribute Capture

**Input (C# code):**
```csharp
[SerializeField]
private int playerHealth;

[Header("Combat")]
public void Attack() { ... }
```

**Parser extracts:**
```python
SymbolInfo(
    name="Attack",
    kind="method",
    class_name="...",
    properties={
        "attributes": ["Header"],
        "attribute_args": {"Header": ["Combat"]}
    }
)
```

**Graph node (downstream):**
```python
GraphNode(
    id="method:src/Player.cs:Attack",
    name="Attack",
    properties={
        "attributes": ["Header"],
        "attribute_args": {"Header": ["Combat"]}
    }
)
```

**Dead-code query:** If `properties["attributes"]` contains framework attributes (e.g., `["SerializedCallback", "Header"]`), exempt from dead-code check.

### Example 2: UE5 Macro Capture

**Input (C++ code):**
```cpp
UCLASS()
class ACharacter : public AActor {
    UPROPERTY(BlueprintReadWrite)
    float Health;

    UFUNCTION(BlueprintCallable)
    void TakeDamage(float Damage) { ... }
};
```

**Parser extracts:**
```python
SymbolInfo(
    name="TakeDamage",
    kind="method",
    class_name="ACharacter",
    properties={
        "ue5_macros": {
            "UFUNCTION": {"BlueprintCallable": True, "BlueprintNativeEvent": False}
        }
    }
)
```

**Graph node (downstream):**
```python
GraphNode(
    id="method:src/Character.h:ACharacter.TakeDamage",
    name="TakeDamage",
    properties={
        "ue5_macros": {
            "UFUNCTION": {"BlueprintCallable": True}
        }
    }
)
```

**Dead-code query (in `dead_code.py`):**
```python
def _is_ue5_blueprint_exposed(node: GraphNode) -> bool:
    macros = node.properties.get("ue5_macros", {})
    ufunction = macros.get("UFUNCTION", {})
    return any([
        ufunction.get("BlueprintCallable"),
        ufunction.get("BlueprintEvent"),
        ufunction.get("BlueprintNativeEvent")
    ])

# In process_dead_code loop:
if _is_ue5_blueprint_exposed(node):
    continue  # Don't flag as dead
```

---

## Integration Points

### 1. **parser_phase.py**

```python
# Line ~43: _PARSER_FACTORIES dict

_PARSER_FACTORIES: dict[str, Callable[[], LanguageParser]] = {
    "python": PythonParser,
    "typescript": lambda: TypeScriptParser(dialect="typescript"),
    "tsx": lambda: TypeScriptParser(dialect="tsx"),
    "javascript": lambda: TypeScriptParser(dialect="javascript"),

    # NEW:
    "csharp": CSharpParser,
    "cpp_ue5": CppUE5Parser,
    "cpp_ue5_build": CppUE5Parser,  # .Build.cs uses same parser as .cpp
    "angelscript": AngelScriptParser,
}

# Existing get_parser() function (lines 61-93) remains unchanged
# The error message (line 88) must be updated to mention new languages
```

### 2. **languages.py**

```python
# Line ~7: SUPPORTED_EXTENSIONS dict

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",

    # NEW:
    ".cs": "csharp",
    ".h": "cpp_ue5",        # Headers (UE5 specific)
    ".cpp": "cpp_ue5",
    ".cc": "cpp_ue5",
    ".cxx": "cpp_ue5",
    ".Build.cs": "cpp_ue5_build",
    ".as": "angelscript",
}
```

### 3. **dead_code.py** (Extended)

```python
# NEW IMPORTS:
from axon.core.ingestion.ue5_utils import (
    is_ue5_blueprint_exposed,
    is_unity_lifecycle_method,
    UE5_BASE_CLASSES,
)

# NEW PREDICATE (after line 78):
def _is_ue5_blueprint_exposed(node: GraphNode) -> bool:
    """Return True if node is a UE5 Blueprint-callable/event/native-event function."""
    return is_ue5_blueprint_exposed(node)

def _is_unity_lifecycle_method(node: GraphNode, label: NodeLabel) -> bool:
    """Return True if method is a Unity lifecycle callback (Start, Update, OnEnable, etc.)."""
    if label != NodeLabel.METHOD:
        return False
    return is_unity_lifecycle_method(node.name, node.class_name)

# NEW EXEMPTION REGISTRY CHECK (after line 86):
def _is_ue5_base_class(node: GraphNode, label: NodeLabel) -> bool:
    """Return True if class extends a known UE5 base class."""
    if label != NodeLabel.CLASS:
        return False
    bases: list[str] = node.properties.get("bases", [])
    return any(base in UE5_BASE_CLASSES for base in bases)

# IN process_dead_code LOOP (line 241-260):
# Add these checks after _is_enum_class check:

if _is_ue5_blueprint_exposed(node):
    continue
if _is_unity_lifecycle_method(node, label):
    continue
if _is_ue5_base_class(node, label):
    continue
```

### 4. **New Module: `ue5_utils.py`**

Create `src/axon/core/ingestion/ue5_utils.py`:

```python
"""UE5 and Unity-specific utilities for dead-code and heritage analysis."""

from __future__ import annotations

import re
from axon.core.graph.model import GraphNode

# UE5 base class registry
UE5_BASE_CLASSES: frozenset[str] = frozenset({
    # Fundamental
    "UObject", "UActorComponent",
    # Characters & Actors
    "AActor", "ACharacter", "APawn", "AController",
    # Gameplay
    "AGameMode", "AGameState", "APlayerController", "APlayerState",
    # UI
    "UWidget", "UUserWidget", "UCanvasPanel",
    # Input
    "UInputComponent",
    # Components
    "USkeletalMeshComponent", "UStaticMeshComponent", "UPrimitiveComponent",
    # Movement
    "UCharacterMovementComponent",
})

UNITY_LIFECYCLE_METHODS: frozenset[str] = frozenset({
    # Core lifecycle
    "Awake", "Start", "Update", "LateUpdate", "FixedUpdate",
    # Physics
    "OnCollisionEnter", "OnCollisionStay", "OnCollisionExit",
    "OnTriggerEnter", "OnTriggerStay", "OnTriggerExit",
    # Enable/Disable
    "OnEnable", "OnDisable", "OnDestroy",
    # UI
    "OnGUI",
})

def is_ue5_blueprint_exposed(node: GraphNode) -> bool:
    """Check if node represents a Blueprint-callable/event function."""
    macros = node.properties.get("ue5_macros", {})
    ufunction = macros.get("UFUNCTION", {})

    if isinstance(ufunction, dict):
        return any([
            ufunction.get("BlueprintCallable"),
            ufunction.get("BlueprintEvent"),
            ufunction.get("BlueprintNativeEvent"),
        ])
    return False

def is_unity_lifecycle_method(method_name: str, class_name: str) -> bool:
    """Check if method name is a Unity lifecycle callback."""
    return method_name in UNITY_LIFECYCLE_METHODS

def parse_uclass_macro(macro_text: str) -> dict[str, bool]:
    """Extract UCLASS macro flags from raw macro text.

    Example: "UCLASS(Blueprintable, Abstract)"
    → {"Blueprintable": True, "Abstract": True}
    """
    flags = {}
    # Simple regex: match comma-separated identifiers inside parentheses
    match = re.search(r"\((.*?)\)", macro_text)
    if match:
        content = match.group(1)
        for flag in re.findall(r"\b([A-Za-z_]\w*)\b", content):
            flags[flag] = True
    return flags

def parse_ufunction_macro(macro_text: str) -> dict[str, bool]:
    """Extract UFUNCTION macro flags from raw macro text.

    Example: "UFUNCTION(BlueprintCallable, Category=\"Combat\")"
    → {"BlueprintCallable": True, "Category": "Combat"}
    """
    flags = {}
    match = re.search(r"\((.*)\)$", macro_text.strip())
    if match:
        content = match.group(1)
        # Extract key=value pairs and bare identifiers
        for kv in re.findall(r"([A-Za-z_]\w*)(?:=(?:\"[^\"]*\"|[^,]*))?", content):
            if kv:
                flags[kv] = True
    return flags
```

---

## Build Order & Dependency Analysis

### Phase 1: C# Parser (Weeks 1-2)

**Why first:**
- Lowest parsing complexity (no macro preprocessing)
- C# attributes are simpler than UE5 macros
- No dependencies on UE5-specific dead-code logic
- Validates parser architecture and testing pattern

**Dependencies:**
- tree-sitter-c-sharp (exists, v0.23+)
- No new model types

**Deliverables:**
- `src/axon/core/parsers/csharp.py` — CSharpParser implementation
- Tests: `tests/core/test_parser_csharp.py` (80+ test cases)
- `languages.py` update: `.cs → "csharp"`
- `parser_phase.py` update: CSharpParser factory

**Validation:**
- Parse real C# Unity project
- Verify class/method/interface extraction
- Verify attribute capture in `properties` dict

### Phase 2: UE5 C++ Parser (Weeks 3-4)

**Why second:**
- More complex macro handling required
- Depends on `ue5_utils.py` being complete
- Needs dead-code exemption logic ready

**Dependencies:**
- tree-sitter-cpp (exists, but may need macro preprocessing layer)
- `ue5_utils.py` module
- `dead_code.py` extensions (Blueprint detection)

**Deliverables:**
- `src/axon/core/parsers/cpp_ue5.py` — CppUE5Parser implementation
- `src/axon/core/ingestion/ue5_utils.py` — Shared utilities
- Extended `dead_code.py` with UE5 Blueprint checks
- Tests: `tests/core/test_parser_cpp_ue5.py` (100+ test cases)
- `languages.py` update: `.h`, `.cpp`, `.Build.cs` → "cpp_ue5"
- `parser_phase.py` update: CppUE5Parser factory

**Macro extraction strategy:**
- Pre-process C++ content to extract UCLASS/UFUNCTION/UPROPERTY macros before tree-sitter
- Regex pattern matching (not perfect but sufficient for metadata storage)
- Store full macro text in `properties["ue5_macros"]` for later inspection

**Challenge:** Macros are not part of the tree-sitter C++ AST — they're handled by preprocessor. Solution:
1. Use regex to extract macro invocations before tree-sitter parsing
2. Attach extracted macro metadata to the nearest symbol
3. Store in `properties` dict for dead-code checks

### Phase 3: AngelScript Parser (Weeks 5-6)

**Why third:**
- Highest risk (community grammar or custom parser)
- Depends on UE5 utilities established in Phase 2
- Can reuse dead-code exemption patterns from Phase 2

**Dependencies:**
- tree-sitter-angelscript (community grammar — needs verification)
- `ue5_utils.py` module
- Extended `dead_code.py` (Phase 2)

**Deliverables:**
- `src/axon/core/parsers/angelscript.py` — AngelScriptParser implementation
- Tests: `tests/core/test_parser_angelscript.py` (80+ test cases)
- `languages.py` update: `.as → "angelscript"`
- `parser_phase.py` update: AngelScriptParser factory

**AngelScript-specific considerations:**
- If tree-sitter-angelscript grammar exists: use it directly
- If not: implement fallback using regex-based minimal parser (functions, classes only)
- Capture UE5-style annotations (e.g., `@BlueprintCallable`) as `properties["ue5_annotations"]`
- Treat similarly to Python/JS: decorators are exemption markers

---

## Schema & Data Model

### No KuzuDB Schema Changes Required

The existing `CodeRelation` REL TABLE GROUP and all node tables can accommodate the three new parsers without schema modifications:

- **New node tables created by KuzuDB schema inference:**
  - `File`, `Folder`, `Function`, `Class`, `Method`, `Interface`, `TypeAlias`, `Enum` (already exist)
  - No new NodeLabel enum entries needed

- **Metadata storage:** All UE5/Unity attributes stored in the existing `properties: JSON` column on graph nodes

**Example KuzuDB query (after indexing):**
```sql
MATCH (f:Function)
WHERE f.properties.ue5_macros.UFUNCTION.BlueprintCallable = true
RETURN f.name, f.file_path
```

### NODE_LABEL Enum: No Changes Needed

Keep existing enum as-is:
```python
class NodeLabel(Enum):
    FILE = "file"
    FOLDER = "folder"
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"
    COMMUNITY = "community"
    PROCESS = "process"
```

**Deferred:** Add `MODULE = "module"` in a later phase for .Build.cs module-level analysis. This would require schema changes and warrant a separate research phase.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Parser Base Classes

**What goes wrong:** Creating a shared `UE5ParserBase` class for CppUE5Parser and AngelScriptParser violates single-responsibility. Each language has unique AST structures; a shared base forces awkward abstractions.

**Instead:** Keep parsers fully independent. Shared UE5 logic goes in `ue5_utils.py` (utility functions, not inheritance).

### Anti-Pattern 2: Storing UE5 Macros as Separate Graph Nodes

**What goes wrong:** Creating `UCLASS` or `UPROPERTY` nodes bloats the graph and breaks the symbol-centric model. Dead-code detection and impact analysis become harder (filtering noise).

**Instead:** Store macros in the `properties` dict on the symbol they decorate. Queries can inspect `properties` without traversing extra edges.

### Anti-Pattern 3: Extending Dead-Code Exemptions in Parsers

**What goes wrong:** Putting exemption logic in parsers couples parsing to dead-code policy. Changing exemption rules requires re-parsing.

**Instead:** All exemption logic stays in `dead_code.py`. Parsers just extract facts into `properties`; dead-code decides significance.

### Anti-Pattern 4: Adding Properties Dynamically After Parsing

**What goes wrong:** Graph phase mutations (e.g., adding `ue5_macros` in heritage phase) are hard to test and debug.

**Instead:** Parsers populate `properties` during parsing. Later phases read but don't modify. This keeps data flow unidirectional.

---

## Testing Strategy

### Parser Test Structure

Each parser gets a dedicated test module with three tiers:

**Tier 1: Symbol Extraction** — Does parser extract correct symbols?
```python
def test_csharp_class_extraction():
    code = """
    public class Player {
        public void Attack() { }
    }
    """
    result = parser.parse(code, "Player.cs")
    assert len(result.symbols) == 2  # class + method
    assert result.symbols[0].name == "Player"
    assert result.symbols[0].kind == "class"
```

**Tier 2: Metadata Capture** — Are attributes/macros captured in properties?
```python
def test_csharp_attribute_capture():
    code = """
    [SerializeField]
    private int health;
    """
    result = parser.parse(code, "Player.cs")
    assert result.symbols[0].properties["attributes"] == ["SerializeField"]
```

**Tier 3: Integration with Dead-Code** — Are exemptions applied correctly?
```python
def test_ue5_blueprint_callable_not_dead():
    # Full graph: C++ code with BlueprintCallable function
    # Process dead_code phase
    # Assert function is_dead == False
    pass
```

### Dead-Code Test Extensions

Extend existing `tests/core/test_dead_code.py` with:

```python
def test_ue5_blueprint_callable_exempt():
    graph = KnowledgeGraph()
    func_node = GraphNode(
        id="function:src/Character.cpp:TakeDamage",
        label=NodeLabel.FUNCTION,
        name="TakeDamage",
        properties={"ue5_macros": {"UFUNCTION": {"BlueprintCallable": True}}}
    )
    graph.add_node(func_node)
    # No incoming CALLS edges
    dead_count = process_dead_code(graph)
    assert dead_count == 0
    assert not func_node.is_dead

def test_unity_lifecycle_method_exempt():
    graph = KnowledgeGraph()
    method_node = GraphNode(
        id="method:src/Player.cs:Player.Start",
        label=NodeLabel.METHOD,
        name="Start",
        class_name="Player"
    )
    graph.add_node(method_node)
    dead_count = process_dead_code(graph)
    assert dead_count == 0
    assert not method_node.is_dead
```

---

## Scalability Considerations

### Parser Performance

| Concern | Current | Strategy |
|---------|---------|----------|
| **Large C++ files (100K+ LOC)** | tree-sitter handles incrementally | Rely on tree-sitter streaming; no batching needed |
| **Macro preprocessing overhead** | Regex scanning before parse | Cache regex results per file; offload to separate thread |
| **Memory per parser instance** | ~2-5MB (tree-sitter Language + Parser) | Cache per language in `_PARSER_CACHE` (existing pattern) |
| **Parsing 10K C# files** | Sequential per file in ThreadPoolExecutor | Existing pool size (8 workers) scales; no changes needed |

### Graph Model Impact

| Concern | At 10K symbols | At 100K symbols | Mitigation |
|---------|----------------|-----------------|-----------|
| **`properties` dict size** | ~100KB (JSON per node) | ~1MB | Lazy load properties only on demand; store compact |
| **Heritage edges (EXTENDS)** | ~1K edges | ~10K edges | Existing edge model sufficient; BFS traversal remains O(1) |
| **Dead-code checks** | ~50ms (loop + property inspection) | ~500ms | No impact; dead-code is single-threaded final pass |

---

## Phase-Specific Research Flags

| Phase | Topic | Research Needed | Priority |
|-------|-------|-----------------|----------|
| Phase 2 (UE5 C++) | C++ macro extraction accuracy | Validate regex patterns against real UE5 codebase; may need AST-level macro extraction if regex fails | HIGH |
| Phase 2 | .Build.cs file structure | Confirm .Build.cs contains module dependencies; design MODULE node integration strategy | MEDIUM |
| Phase 3 (AngelScript) | Grammar availability | Verify tree-sitter-angelscript exists and is maintained; if not, decide between custom parser or regex fallback | HIGH |
| Phase 3 | AngelScript UE5 annotations | Confirm annotation syntax (@BlueprintCallable vs UFUNCTION equivalents); validate against real UnrealAngel examples | MEDIUM |

---

## Risk Assessment

### Low Risk
- C# parsing: Grammar is mature (v0.23+), extensive test coverage
- No KuzuDB schema changes needed
- Isolated parser additions (no core pipeline modification)

### Medium Risk
- UE5 macro extraction: Regex-based; may miss edge cases or newer macro patterns
- .Build.cs integration: Unclear if they should be separate nodes or metadata on C++ classes

### Mitigations
- Validate macro extraction against real UE5 source code (available per PROJECT.md)
- Test on both simple and complex UE5 projects
- Design .Build.cs handling carefully; may defer MODULE node type to Phase 2 milestone end

---

## Deferred: MODULE Node Type

**Decision:** Add `NodeLabel.MODULE` in a follow-up phase (not v1).

**Rationale:**
- .Build.cs files can be parsed as C++ (limited parsing) with metadata in properties for now
- Module dependency edges (DEPENDS_ON) require a separate ingestion phase after all files parsed
- Current priority is getting symbol-level analysis working; modular analysis is secondary

**Future phase requirements:**
- Add `MODULE = "module"` to NodeLabel enum
- Create `module_discovery.py` phase to:
  1. Scan all .Build.cs files
  2. Extract `PublicDependencyModuleNames`, `PrivateDependencyModuleNames`
  3. Create MODULE nodes + DEPENDS_ON edges
- Update KuzuDB schema to add `Module` table and `DEPENDS_ON` REL TABLE
- Update dead-code logic: don't flag MODULE-level exports as dead

---

## References

**Tree-Sitter Grammars (verified):**
- tree-sitter-c-sharp: v0.23.1 (Nov 2024), 590 commits, 37 contributors, actively maintained
- tree-sitter-cpp: 442 commits, 36+ contributors, actively maintained
- tree-sitter-angelscript: [REQUIRES VALIDATION] — check PyPI and GitHub

**Existing Axon Architecture:**
- `/axon/.planning/codebase/ARCHITECTURE.md` — Overall system design
- `/axon/src/axon/core/parsers/base.py` — LanguageParser protocol
- `/axon/src/axon/core/parsers/typescript.py` — Reference implementation
- `/axon/src/axon/core/ingestion/dead_code.py` — Exemption pattern guide

---

*Architecture research: 2026-03-23*
