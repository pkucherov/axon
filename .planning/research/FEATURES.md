# Feature Landscape: C#, UE5 C++, AngelScript Parsers

**Domain:** Code intelligence engine language extension
**Languages:** C# (Unity + .NET), UE5 C++, UnrealAngel AngelScript
**Researched:** 2026-03-23
**Confidence:** MEDIUM (tree-sitter capabilities confirmed; UE5 macro details from public docs; AngelScript ecosystem fragmented)

## Executive Summary

Three new parsers extend Axon's code intelligence to game development and backend ecosystems. Each parser must extract symbols, imports, calls, and type references via tree-sitter, matching the `ParseResult` schema established by Python and TypeScript parsers. Beyond baseline extraction, UE5 C++ gains macro-aware metadata (UCLASS/UFUNCTION specifiers) and Blueprint exposure flags to prevent false dead-code positives. C# gains Unity lifecycle method exemption. AngelScript, less standardized, requires a community tree-sitter grammar choice but follows the same extraction pattern.

The downstream benefit is immediate: Axon's dead-code detection, call graph visualization, and module analysis work out-of-the-box for UE5 projects and Unity codebases once parsers emit symbols with the right metadata (decorators field for UE5 macros, is_entry_point for lifecycle methods).

## Key Finding: Macro Extraction as Metadata

UE5 macros (UCLASS, UFUNCTION, UPROPERTY, USTRUCT, UENUM) are **not separate nodes** — they're preprocessor directives that annotate type definitions. Tree-sitter-cpp parses these as attribute-like constructs (via preprocessor or C++ attribute syntax). Parsers must extract macro arguments as decorator metadata (e.g., `decorators: ["UCLASS", "BlueprintType", "Blueprintable"]`) rather than create separate graph nodes. This keeps the graph model simple and leverages existing dead-code exemption logic.

---

## C# (Unity + .NET)

### Table Stakes: What Axon Breaks Without

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Functions** | Core symbol type; graph cannot exist without it | Low | `function_declaration` or `method_declaration` with `static` modifier |
| **Methods** | Core symbol type; classes without methods are incomplete | Low | `method_declaration` with receiver (belongs to class) |
| **Classes** | Organizing unit for methods; dead-code needs class context | Low | `class_declaration`; extract name, start/end lines, content |
| **Interfaces** | Type contracts; required for IMPLEMENTS edges | Medium | `interface_declaration`; similar to classes but distinct kind |
| **Properties** | Visual in UE5/Blueprint contexts; often public API | Low | `property_declaration` with get/set; extract as symbol kind `"property"` |
| **Imports** | Dependency resolution; module navigation | Medium | `using` statements (absolute or relative); resolve to module paths |
| **Type References** | Heritage (IMPLEMENTS/EXTENDS); type_refs for unused types | Low | From method signatures, parameter types, return types, variable annotations |
| **Inheritance** | EXTENDS/IMPLEMENTS edges feed dead code and community detection | Low | Base class/interface list in class declaration |
| **Calls** | Dead code detection depends on incoming CALLS edges | Medium | Method calls, static function calls; extract receiver and target name |
| **Modifiers** | Public/private affect dead code and API surface | Low | Extract from `modifier` list (public, private, protected, internal, static, virtual, abstract) |

### Differentiators: High Value, Not Expected

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Unity Lifecycle Exemption** | MonoBehaviour methods (Start, Update, etc.) never dead; Axon avoids false positives | Medium | Hardcode list: Start, Update, FixedUpdate, LateUpdate, Awake, OnEnable, OnDisable, OnDestroy, OnCollisionEnter, OnCollisionExit, OnCollisionStay, OnCollisionEnter2D, OnCollisionExit2D, OnCollisionStay2D, OnTriggerEnter, OnTriggerExit, OnTriggerStay, OnTriggerEnter2D, OnTriggerExit2D, OnTriggerStay2D, OnGUI, OnMouseDown, OnMouseUp, OnMouseDrag, OnMouseEnter, OnMouseExit, OnMouseOver, OnPreRender, OnPostRender, OnApplicationFocus, OnApplicationPause, OnApplicationQuit, OnValidate, OnBecameVisible, OnBecameInvisible. Check if method name matches + is public + method has no parameters. |
| **[SerializeField] / [Header] Detection** | Metadata for UI visualization; fields exposed in inspector are part of public API | Low | Extract custom attributes from `attribute_list`; store in `properties` dict or `decorators` list |
| **MonoBehaviour Inheritance Detection** | Automatically exempt public methods on classes inheriting from MonoBehaviour | Medium | Check EXTENDS edge to "MonoBehaviour"; if yes, exempt public methods from dead code |
| **[RequireComponent] Dependencies** | Component dependencies; architectural metadata | Low | Extract as decorator; useful for downstream graph queries |
| **.NET Standard Library Types** | Know System.*, UnityEngine.* types are not dead code | Medium | Hardcode list similar to Python builtins; or: any type in "System" or "UnityEngine" namespace never flagged as missing type |

### Anti-Features: Explicitly NOT Build in V1

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full Roslyn Semantic Analysis** | Requires C# runtime; C# semantic resolution is complex and slow | Tree-sitter structural parsing is sufficient; leave semantic validation to IDE/compiler |
| **async/await Unwrapping** | Would require task graph unwinding; overly complex for v1 | Parse `async` keyword as decorator; treat async methods normally; let dead code see them via CALLS |
| **Generics Specialization** | Would require type resolution; beyond tree-sitter scope | Extract generic type parameters as-is; don't specialize; generic classes treated as single entity |
| **Reflection-based Dead Code Exemption** | Would require runtime; not practical in static analysis | Use decorators and type names instead; developer must annotate with [UsedImplicitly] or similar if Roslyn can't see it |
| **.uasset (Binary Asset) Parsing** | Binary format; not practical with tree-sitter | Out of scope; focus on code |

### Complexity Notes

- **Properties with getters/setters**: Must distinguish between auto-property and full property declaration; extract each as a single symbol, not separate getter/setter symbols
- **Attributes with arguments**: `[SerializeField(order = 5)]` — extract attribute name and store full text; parser doesn't need to parse argument syntax
- **Inheritance with generics**: `class Derived<T> : Base<T>` — extract "Base" as parent name; don't specialize

---

## UE5 C++ (Unreal Engine 5)

### Table Stakes: What Axon Breaks Without

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Functions** | Core symbol; standalone or member | Low | `function_declaration`; may be inside UFUNCTION macro or not |
| **Methods** | Class member functions | Low | Inside `class_definition` or `struct_definition`; extract class_name field |
| **Classes / Structs** | Organizing unit for methods; EXTENDS/IMPLEMENTS edges | Low | Both handled as "class" kind; tree-sitter-cpp parses struct_specifier and class_specifier |
| **Imports / Includes** | Module dependency; file includes via #include | Medium | Extract `#include` directives; resolve relative (local) vs angle-bracket (system); store as ImportInfo |
| **Type References** | Parameter types, return types, variable declarations | Medium | From function signatures; avoid primitive types (int, float, bool, void, etc.) |
| **Inheritance** | Base class list; EXTENDS edges feed dead code | Low | Extract from `base_class_clause` or similar; handles public/private/protected inheritance |
| **Calls** | Dead code depends on incoming CALLS edges | Medium | Function calls via tree-sitter-cpp `call_expression` |
| **Enums** | Enum class/struct definitions | Low | Extract as symbol kind "enum"; useful for type refs |
| **Structs vs Classes** | Semantic distinction in UE5 (usually different purposes) | Low | Extract both; mark kind as "class" or "struct" separately if needed for dead code logic |

### Differentiators: UE5-Critical Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **UCLASS/USTRUCT/UENUM Macro Extraction** | Annotation metadata; makes class ownership and reflection status visible in graph queries | High | Macros appear as `#define` or preprocessor invocations. For UCLASS before class definition, extract macro arguments (BlueprintType, Blueprintable, etc.) as decorator strings. Tree-sitter-cpp doesn't parse macro *expansion*, but it does tokenize the directive. Fallback: regex on raw source if needed. Store in `decorators: ["UCLASS", "BlueprintType", ...]` |
| **UFUNCTION Specifiers: Blueprint Exposure** | BlueprintCallable, BlueprintEvent, BlueprintNativeEvent, BlueprintPure functions must NEVER be flagged as dead code | High | Extract macro specifiers and store in decorators. In dead_code.py, add exemption: if "BlueprintCallable" or "BlueprintEvent" or "BlueprintPure" in decorators, skip dead-code flag. Same for BlueprintNativeEvent. |
| **UPROPERTY Metadata** | EditAnywhere, VisibleAnywhere, BlueprintReadOnly, BlueprintReadWrite flag exported properties | Medium | Extract from UPROPERTY macro; store decorators; useful for UI visualization but not critical for dead-code logic |
| **UE5 Base Class Registry** | Never flag AActor, UObject, UActorComponent, etc. as unknown or dead | High | Hardcode list in dead_code.py + parser metadata: if class extends from known UE5 base (via inheritance graph), never dead. List: UObject, AActor, APawn, ACharacter, AGameMode, AGameState, APlayerController, APlayerState, AGameModeBase, UActorComponent, USceneComponent, UPrimitiveComponent, UWidget, FString, FName, FVector, etc. |
| **Module Nodes (.Build.cs Parsing)** | Module dependencies + architecture visibility; MODULE nodes with DEPENDS_ON edges | High | .Build.cs is JSON-like or Python-like; can use tree-sitter-json or simple regex. Extract `PublicDependencyModuleNames`, `PrivateDependencyModuleNames` from Build.cs file; emit MODULE nodes and DEPENDS_ON edges. Requires new NodeLabel.MODULE type in model.py. |
| **Macro Specifiers as Exemptions** | Functions marked UENUM_CLASS, USTRUCT(meta=), etc. may have special semantics that prevent dead code | Medium | Extract all macro args; store as decorators; let dead_code.py decide based on pattern matching |

### Anti-Features: Explicitly NOT Build in V1

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full UHT (Unreal Header Tool) Simulation** | Would require understanding of .generated.h files, reflection system, and full macro expansion | Parse UCLASS/UFUNCTION as-is via raw text extraction; don't try to expand macros |
| **Compiled Reflection Parsing** | Would require linking against UE5 libs; not practical in static analysis | Static parsing only; rely on source annotations |
| **.uasset (Binary Asset) Graph Edges** | Binary format; tree-sitter can't help | Deferred to future phases; focus on code |
| **Non-UE5 C++ Support** | Too broad; UE5 macros are dialect-specific | V1 targets UE5 only; standard C++ without UE5 macros will parse structurally but miss semantic metadata |
| **Template Specialization** | Would require type resolution; beyond tree-sitter scope | Parse template definitions as-is; don't specialize; generic classes treated as single entity |

### Complexity Notes

- **Preprocessor Macros**: Tree-sitter-cpp parses preprocessor directives as nodes (preproc_directive_in_function_body, preproc_function_definition, etc.). UCLASS and UFUNCTION are C++ function-like macros. You must regex-extract the content: `UCLASS(BlueprintType, Blueprintable)` → capture args and store as decorator list. Macro expansion is **not** tree-sitter's job.
- **Include Paths**: Resolve <angle.h> to external; "quotes/local" to local repo. Store both as ImportInfo; downstream ingestion phase handles resolution.
- **Inline Functions**: May appear in headers; extract like any function.
- **Constexpr / Concepts**: C++20 features; tree-sitter-cpp supports them; extract as modifiers or decorators.
- **#if Blocks**: Tree-sitter parses conditionally compiled code as separate branches. Extract symbols from all branches; downstream analysis can deal with multiplicity.

### UE5 Base Classes Hardcoded List

**Should never be flagged as dead or missing:**

Core object system:
- UObject
- UClass
- UProperty
- UFunction
- UInterface
- UEnum
- UStruct

Actor system:
- AActor
- APawn
- ACharacter
- AGameMode
- AGameModeBase
- AGameState
- APlayerController
- APlayerState
- AController
- ADefaultPawn

Component system:
- UActorComponent
- USceneComponent
- UPrimitiveComponent
- USkeletalMeshComponent
- UStaticMeshComponent
- UCapsuleComponent
- USphereComponent
- UBoxComponent

Widget (Slate) system:
- UWidget
- UUserWidget
- UButton
- UTextBlock
- UImage
- UCanvasPanel
- UScrollBox
- UComboBox

Math / Data:
- FVector
- FRotator
- FTransform
- FString
- FName
- FText
- FLinearColor
- FMatrix
- FQuat

### UE5 Blueprint Specifiers Requiring Dead-Code Exemption

**UFUNCTION specifiers that indicate Blueprint exposure:**
- BlueprintCallable → Can be called from Blueprint
- BlueprintEvent → Blueprint-overridable
- BlueprintNativeEvent → Hybrid (native + Blueprint override)
- BlueprintPure → No side effects; usable in expressions
- BlueprintImplementableEvent → Blueprint-only implementation

**UCLASS specifiers that affect semantics:**
- Blueprintable → Can be placed in editor
- BlueprintType → Can be used as a type in Blueprint
- NotBlueprintable → Explicitly not Blueprint-exposed
- Abstract → Cannot instantiate directly
- Deprecated → Should not be used

---

## UnrealAngel AngelScript

### Table Stakes: What Axon Breaks Without

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Functions** | Core symbol; same as C++/C# | Low | `function_declaration` node type (varies by grammar choice) |
| **Methods** | Class member functions | Low | Inside class definition; extract class_name |
| **Classes** | Organizing unit for methods | Low | `class_declaration` or `class_definition` |
| **Imports** | Module system; #include or import statements | Medium | AngelScript supports `#include` and `import` syntax (varies by grammar) |
| **Type References** | Parameter/return/variable types | Low | From function signatures |
| **Inheritance** | EXTENDS edges; AngelScript uses `:` syntax | Low | Base class list in class definition |
| **Calls** | Dead code depends on CALLS edges | Medium | Function calls via call expressions |
| **Enums** | Enum definitions | Low | AngelScript supports enum class definitions |

### Differentiators: UE5 Integration

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Hazelight UnrealAngel Dialect Detection** | AngelScript can run in vanilla or UE5-modified form; UnrealAngel is the UE5 fork with UFUNCTION-like macros | High | Community tree-sitter grammars vary. Some support "mixin" classes and UE-style inheritance. Must choose grammar that handles: (1) standard AS syntax, (2) UE-style UCLASS/UFUNCTION if present in dialect. Hardest differentiator; grammar choice is **critical**. |
| **UCLASS/UFUNCTION Annotation Handling** | UnrealAngel may use UE5 macro annotations or AS-native syntax | Medium | If using dimitrijejankov/tree-sitter-unreal-angelscript (appears Unreal-specific), should have macro extraction built in. Otherwise, apply same regex extraction as C++ |
| **Mixin Class Support** | UnrealAngel supports mixins (composition pattern); important for architecture | Low | Extract as class with special marker; store kind as "mixin" if grammar supports |
| **UE5 Base Class Registry** | Same as C++; UObject, AActor, etc. never dead | High | Same hardcoded list as C++; most UE5 AS code inherits from UE base classes |

### Anti-Features: Explicitly NOT Build in V1

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full Script Compilation** | Would require Unreal's script compiler; not practical | Static parsing only |
| **Runtime Behavior Prediction** | Script dispatch via reflection is dynamic; can't predict at static analysis time | Extract symbols; let call graph approximate behavior |
| **Vanilla AngelScript + UE5 Mixing** | AngelScript exists in multiple flavors; keeping both working is complex | V1 targets UnrealAngel/Hazelight dialect only; vanilla AS deferred |

### Complexity Notes

- **Grammar Fragmentation**: Five community tree-sitter grammars exist for AngelScript. The critical choice: `dimitrijejankov/tree-sitter-unreal-angelscript` (most likely UE5-aware) vs others. Must validate that chosen grammar extracts classes, methods, imports correctly. **Action item: Validate one grammar before v1 release.**
- **AS Syntax Differences**: AngelScript uses `::` for scope resolution, `:` for inheritance, `[]` for array syntax. Tree-sitter should handle all; verify in grammar.
- **Property Syntax**: AngelScript has property getters/setters similar to C#; extract as single symbol like C#.
- **Function Overloading**: AngelScript supports overloads; each overload is a separate symbol (same name, different signature). Keep them separate or merge by signature? **Recommendation: Keep separate; dead code can see each overload's call edges independently.**
- **Module System**: AngelScript has a module/namespace system; may use `#include` or `namespace` syntax. Extract both as import relationships.

### AngelScript Language Assumptions for Parser

Based on angelcode.com and community grammars:

**Symbol Types to Extract:**
- `function` - global functions and methods
- `class` - class definitions
- `interface` - interface definitions (if supported by dialect)
- `enum` - enum definitions
- `property` - property declarations with getters/setters
- `struct` - struct definitions (if distinct from class in dialect)

**Syntax Patterns:**
- Inheritance: `class Derived : Base` or `class Derived : Base1, Base2`
- Type annotations: `returnType funcName(paramType paramName)`
- Calls: `funcName()` or `obj.method()`
- Imports: `#include "module"` or dialect-specific `import` statement

---

## Feature Dependencies

```
graph TD
    A["Symbols (functions, methods, classes)"] --> B["Type References"]
    A --> C["Calls"]
    A --> D["Inheritance"]
    B --> E["Dead Code Detection"]
    C --> E
    D --> E
    F["Decorators / Macros"] --> E
    G["Lifecycle Exemptions (C#)"] --> E
    H["Blueprint Exemptions (UE5 C++)"] --> E
    I["UE5 Base Class Registry"] --> E

    J["Imports"] --> K["Module Graph"]
    K --> L["Community Detection"]

    M["Module Nodes (UE5)"] --> K
    M --> L
```

**Dependency Order for Implementation:**
1. Core extraction (symbols, imports, calls, types) — all three languages
2. Inheritance (EXTENDS/IMPLEMENTS) — all three languages
3. Decorators/macros extraction — C# (attributes), UE5 C++ (macros), AngelScript (dialect-specific)
4. Dead-code exemptions — leverage decorators + hardcoded lists
5. Module nodes (UE5 only) — .Build.cs parsing + MODULE edges

**Blocking Relationships:**
- Dead code detection **requires** symbols + calls + inheritance
- Decorators are **optional** for baseline graph but **required** for UE5 correctness
- Module nodes are **deferred** if .Build.cs parsing proves complex

---

## MVP Recommendation

### Phase 1: Baseline Parsing (all three languages)

Prioritize:
1. **C# Functions, Methods, Classes** — TypeScript parser already does this; C# should be straightforward
2. **C# Imports** — `using` statements; map to module paths
3. **UE5 C++ Functions, Methods, Classes, Structs** — tree-sitter-cpp is mature
4. **UE5 C++ Includes** — resolve .h includes; map to modules
5. **AngelScript Symbols & Imports** — validate tree-sitter grammar works; extract baseline

Goals: All three languages produce valid ParseResult; graph ingestion works; symbols appear in web UI.

### Phase 2: Type & Call Extraction

Prioritize:
1. **Type References** (all languages) — parameter types, return types, variable annotations
2. **Calls** (all languages) — method calls, function calls; receiver + target name
3. **Inheritance** (all languages) — EXTENDS/IMPLEMENTS edges

Goals: Dead-code detection can run; call graph visible; false positives emerge.

### Phase 3: UE5-Specific & Dead-Code Correctness

Prioritize:
1. **UE5 Macro Extraction** — UCLASS/UFUNCTION/UPROPERTY decorator strings
2. **Blueprint Exposure Exemptions** — dead_code.py extended for BlueprintCallable, etc.
3. **UE5 Base Class Registry** — hardcoded list in dead_code.py
4. **C# Unity Lifecycle Exemptions** — hardcoded list in dead_code.py
5. **C# MonoBehaviour Detection** — EXTENDS MonoBehaviour exempts public methods

Goals: UE5 and Unity codebases have minimal dead-code false positives; graph is semantically correct.

### Phase 4: Module Nodes (if time permits)

1. **UE5 .Build.cs Parsing** — extract module names and dependencies
2. **MODULE NodeLabel & Schema** — add to model.py
3. **DEPENDS_ON Edges** — emit between modules

Goals: Architecture-level view; module-scoped dead code; project structure visible.

### Defer to Later Phase

- **C# .NET Standard Library Registry** — can add incrementally as false positives emerge
- **AngelScript Dialect Validation** — validate chosen grammar empirically; document assumptions
- **Template/Generic Specialization** — keep as future enhancement
- **Vanilla AngelScript Support** — focus on UnrealAngel only in v1

---

## Sources

### C# & .NET
- tree-sitter-c-sharp grammar: https://github.com/tree-sitter/tree-sitter-c-sharp (grammar.js inspected; supports C# 1.0-13.0)
- Unity MonoBehaviour lifecycle: https://docs.unity3d.com/ScriptReference/MonoBehaviour.html (HIGH confidence; official docs)
- C# attributes: From grammar analysis; modifiers + attribute_list nodes confirmed

### UE5 C++
- tree-sitter-cpp grammar: https://github.com/tree-sitter/tree-sitter-cpp (grammar.js inspected; C++11-20 support)
- UE5 Macro Specifiers: Public knowledge from UE5 dev forums and source; UFUNCTION, UCLASS, BlueprintCallable, etc. widely documented (MEDIUM confidence on exact specifier list; may need validation against UE5.4+ docs)
- UE5 Base Classes: From engine source; AActor, UObject, APawn, etc. widely known (HIGH confidence)

### AngelScript
- AngelScript Home: https://www.angelcode.com/angelscript/ (official; MEDIUM confidence on language feature set; manual not fully accessible)
- Tree-sitter AngelScript Grammars: 5 community implementations found via GitHub search; most active appear C-based (MEDIUM confidence; requires empirical validation)
- UnrealAngel: Limited public documentation; referenced in game dev circles; dimitrijejankov/tree-sitter-unreal-angelscript appears most recent (LOW confidence; needs code inspection)

---

## Confidence Assessment

| Area | Level | Notes |
|------|-------|-------|
| **C# Baseline Extraction** | HIGH | tree-sitter-c-sharp is official; grammar is comprehensive; extraction mirrors Python/TS parser |
| **C# Unity Lifecycle Methods** | HIGH | Official Unity docs enumerate all callbacks; hardcoded list is stable |
| **UE5 C++ Baseline Extraction** | HIGH | tree-sitter-cpp is official; C++14/17/20 support confirmed |
| **UE5 Macro Extraction** | MEDIUM | Macro expansion itself is complex; regex-based decorator extraction should work but needs testing against real UE5 code |
| **UE5 Base Class List** | HIGH | AActor, UObject, etc. are stable across UE versions; hardcoded list will not change |
| **UE5 Blueprint Specifiers** | MEDIUM | BlueprintCallable, etc. are documented but may have version-specific variations; list is representative |
| **AngelScript Grammar Choice** | LOW | Five grammars exist; which is best for UnrealAngel is unclear; needs empirical validation |
| **AngelScript UE5 Integration** | LOW | Hazelight UnrealAngel dialect is underdocumented; assumptions about UCLASS/UFUNCTION support are unverified |
| **Module Parsing (.Build.cs)** | MEDIUM | JSON-like format; tree-sitter-json or regex feasible; implementation blocked on format validation against real projects |

---

## Gaps to Address

### Before Phase 1 Release

- [ ] Validate tree-sitter-c-sharp attribute_list extraction works with [SerializeField], [Header], etc.
- [ ] Test tree-sitter-cpp preprocessor macro parsing on real UE5 headers; validate UCLASS/UFUNCTION are captured as nodes
- [ ] Choose final AngelScript tree-sitter grammar; inspect grammar.js for symbol extraction capability
- [ ] Confirm C# import resolution logic (using System.X → module mapping)

### Before Phase 3 Release

- [ ] Collect real UE5 codebase; test Blueprint exposure detection on actual UFUNCTION macros
- [ ] Collect Unity codebase; validate lifecycle method exemption works
- [ ] Document macro specifier extraction regex/logic; ensure robustness

### Deferred to Future Phases

- [ ] Module node implementation (blocked on .Build.cs format validation)
- [ ] AngelScript dialect-specific features (blocked on UnrealAngel documentation)
- [ ] C# .NET Standard Library registry (can add incrementally as needed)
- [ ] Template specialization for C++ and C# generics (complex; lower priority)
