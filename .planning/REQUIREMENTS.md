# Requirements — Axon Language Extension: C#, UE5 C++, AngelScript

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: Register C# language in `languages.py` with `.cs` extension mapping
- [ ] **INFRA-02**: Register C++ language in `languages.py` with `.h` and `.cpp` extension mappings
- [ ] **INFRA-03**: Register AngelScript language in `languages.py` with `.as` extension mapping
- [ ] **INFRA-04**: Register `.Build.cs` files as a distinct parseable type (e.g., `csharp-build`) in `languages.py`
- [ ] **INFRA-05**: Add `tree-sitter-c-sharp` and `tree-sitter-cpp` as dependencies in `pyproject.toml`
- [ ] **INFRA-06**: Build or vendor a Python binding for `Relrin/tree-sitter-angelscript` and integrate it into the project

### C# Parser

- [ ] **CS-01**: User can index a C# file and see Function, Method, Class, and Interface nodes in the graph
- [ ] **CS-02**: User can see IMPORTS edges between .cs files based on `using` directive resolution
- [ ] **CS-03**: User can see EXTENDS/IMPLEMENTS edges between C# classes and interfaces
- [ ] **CS-04**: C# properties (get/set accessors) are extracted as Method nodes with their parent class set
- [ ] **CS-05**: Unity lifecycle methods (Start, Update, Awake, LateUpdate, FixedUpdate, OnDestroy, OnEnable, OnDisable, OnTriggerEnter, OnCollisionEnter, OnCollisionExit, OnTriggerExit, Reset, OnValidate, and the 10 others) are never flagged as dead code
- [ ] **CS-06**: C# partial classes spread across multiple files are merged into a single Class node (or their methods attributed to a common class_name) without duplicating the class node

### UE5 C++ Parser

- [ ] **CPP-01**: User can index a UE5 .h or .cpp file and see Function, Method, Class, and Struct nodes in the graph
- [ ] **CPP-02**: UCLASS, USTRUCT, and UENUM macro specifiers are stored as metadata in the Class/Struct node's `properties` dict (e.g., `properties["ue_specifiers"] = ["BlueprintType", "Blueprintable"]`)
- [ ] **CPP-03**: UFUNCTION macro specifiers are stored as metadata in the Method/Function node's `properties["ue_specifiers"]` list
- [ ] **CPP-04**: UPROPERTY macro specifiers are stored as metadata in a Property node's `properties["ue_specifiers"]` list
- [ ] **CPP-05**: Functions/methods with BlueprintCallable, BlueprintEvent, BlueprintNativeEvent, or BlueprintPure in their UFUNCTION specifiers are never flagged as dead code
- [ ] **CPP-06**: UE5 framework base classes (AActor, UObject, UActorComponent, ACharacter, AGameMode, APlayerController, UWidget, UUserWidget, UGameInstance, APawn, AController, UBlueprintFunctionLibrary, and equivalent common classes) are treated as known external types — not flagged as unknown or unresolved
- [ ] **CPP-07**: User can see EXTENDS edges from UE5 C++ class declarations (`:` inheritance syntax) to parent classes
- [ ] **CPP-08**: `#include` directives in .h/.cpp files are extracted and contribute to IMPORTS edges where the target file exists in the indexed repo

### AngelScript Parser

- [ ] **AS-01**: User can index a UnrealAngel .as file and see Function, Method, and Class nodes in the graph
- [ ] **AS-02**: User can see EXTENDS edges from AngelScript class declarations to parent classes
- [ ] **AS-03**: UE5-style annotations in AngelScript (UCLASS, UFUNCTION equivalents, mixin class markers) are extracted and stored in node `properties["ue_specifiers"]`
- [ ] **AS-04**: AngelScript import/include directives are extracted and contribute to IMPORTS edges where targets exist in the indexed repo

### Module Nodes

- [ ] **MOD-01**: `NodeLabel.MODULE` is added to `model.py` and a corresponding MODULE table is created in KuzuDB schema
- [ ] **MOD-02**: `RelType.DEPENDS_ON` is added to `model.py` for module dependency edges
- [ ] **MOD-03**: `.Build.cs` files are parsed to extract the module name and `PublicDependencyModuleNames`/`PrivateDependencyModuleNames` lists
- [ ] **MOD-04**: Each parsed `.Build.cs` file emits one MODULE node with the module name as its `name` property and the `.Build.cs` path as `file_path`
- [ ] **MOD-05**: DEPENDS_ON edges are emitted between MODULE nodes based on the dependency lists in `.Build.cs`

---

## v2 Requirements (deferred)

- Full UHT `.generated.h` file parsing — binary/generated format; too complex for v1
- Blueprint visual scripting graph parsing (`.uasset`) — binary format, not tree-sitter parseable
- Roslyn-level C# semantic analysis — structural parsing sufficient for graph
- C++/CLI mixed-mode support — non-UE5 C++ out of scope for v1
- Deeper AngelScript UE5 macro equivalents beyond basic class annotations
- Cross-file C# partial class semantic merging beyond same-class-name grouping

---

## Out of Scope

- C++/CLI or non-UE5 C++ codebases — v1 targets UE5 specifically; general C++ would need a separate parser configuration
- Unity-specific script lifecycle for non-MonoBehaviour classes — only MonoBehaviour subclass exemptions in v1
- Game-specific runtime analysis (profiling, memory, blueprint execution) — static graph analysis only
- `.uasset` / `.umap` binary asset parsing — requires Epic's proprietary tools, not tree-sitter
- Generating or modifying UE5 code — read-only analysis tool

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 through INFRA-04 | Phase 1 | — |
| INFRA-05 | Phase 1 | — |
| INFRA-06 | Phase 3 (spike) | — |
| CS-01 through CS-04 | Phase 1 | — |
| CS-05 through CS-06 | Phase 2 | — |
| CPP-01 through CPP-04 | Phase 2 | — |
| CPP-05 through CPP-08 | Phase 2 | — |
| AS-01 through AS-04 | Phase 3 | — |
| MOD-01 through MOD-05 | Phase 4 | — |
