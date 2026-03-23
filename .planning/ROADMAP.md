# Roadmap — Axon Language Extension: C#, UE5 C++, AngelScript

**Project:** Axon Language Extension: C#, UE5 C++, AngelScript Parsers
**Milestone:** v1 Language Support
**Created:** 2026-03-23
**Granularity:** Standard (6 phases, 3-5 plans each)
**Coverage:** 29/29 v1 requirements mapped

---

## Phases

- [ ] **Phase 1: C# Parser Foundation** - Implement tree-sitter-based C# parser; establish parser pattern for downstream phases
- [ ] **Phase 2: AngelScript Binding Spike** - Research and build/vendor custom Python binding for tree-sitter-angelscript; validate grammar capability
- [ ] **Phase 3: UE5 C++ Parser & Macro Extraction** - Implement C++ parser with UCLASS/UFUNCTION/UPROPERTY metadata extraction; highest complexity and risk
- [ ] **Phase 4: AngelScript Parser Implementation** - Implement AngelScript parser reusing C++ patterns; depends on Phase 2 binding availability
- [ ] **Phase 5: Dead-Code Exemptions & Unity Integration** - Extend dead_code.py with Blueprint exposure detection, UE5 base class registry, and Unity lifecycle method exemptions
- [ ] **Phase 6: Module Nodes & Cross-Language Validation** - Add MODULE node type, parse .Build.cs files, validate import resolution across all three languages

---

## Phase Details

### Phase 1: C# Parser Foundation

**Goal:** Users can index C# codebases and see complete symbol graphs (functions, methods, classes, interfaces, properties) with type information and imports resolved.

**Depends on:** Nothing (foundation phase)

**Requirements:** INFRA-01, INFRA-05, CS-01, CS-02, CS-03, CS-04

**Success Criteria** (what must be TRUE):
1. User can index a .cs file and see all functions, methods, classes, and interfaces extracted as graph nodes
2. User can inspect C# class inheritance via EXTENDS edges in the graph
3. User can see IMPORTS edges between .cs files based on `using` directive resolution
4. User can see property accessors (get/set) represented as Method nodes within their parent class
5. Property accessors are correctly attributed to their containing class, avoiding duplication

**Plans:** 1/3 plans executed

Plans:
- [x] 01-01-PLAN.md — Infrastructure: pyproject.toml, languages.py, SymbolInfo.properties, graph wiring, test scaffold
- [ ] 01-02-PLAN.md — CSharpParser implementation: symbol extraction, heritage, attributes, using directives, resolve_csharp_imports
- [ ] 01-03-PLAN.md — Pipeline registration: _PARSER_FACTORIES, _qualify_collisions hook, ruff lint, full suite green

---

### Phase 2: AngelScript Binding Spike

**Goal:** Reduce AngelScript implementation risk by validating grammar capability and building/vendoring a working Python binding before full parser implementation.

**Depends on:** Nothing (parallel research, not blocking Phases 1 or 3)

**Requirements:** INFRA-06

**Success Criteria** (what must be TRUE):
1. A Python binding (custom or vendor) for tree-sitter-angelscript is available and importable in the project
2. The binding can parse a sample .as file and return a tree-sitter Tree object
3. The grammar can extract functions, methods, and classes from UnrealAngel AngelScript syntax
4. Grammar limitations are documented and any fallback strategy (regex vs tree-sitter) is decided

**Plans:** TBD

**UI hint**: no

---

### Phase 3: UE5 C++ Parser & Macro Extraction

**Goal:** Users can index UE5 .h and .cpp files with complete symbol extraction and UE5 macro metadata (UCLASS, UFUNCTION, UPROPERTY) extracted and stored as decorators on symbols.

**Depends on:** Phase 1 (parser pattern established)

**Requirements:** INFRA-02, CPP-01, CPP-02, CPP-03, CPP-04, CPP-05, CPP-06, CPP-07, CPP-08

**Success Criteria** (what must be TRUE):
1. User can index a .h or .cpp file and see functions, methods, classes, and structs extracted as nodes
2. UCLASS, USTRUCT, and UENUM macro specifiers are captured and stored in node `properties["ue_specifiers"]`
3. UFUNCTION macro specifiers are captured and stored in Method/Function node `properties["ue_specifiers"]`
4. UPROPERTY macro specifiers are captured and stored in Property node `properties["ue_specifiers"]`
5. User can see EXTENDS edges from C++ class declarations to parent classes (`:` inheritance syntax)
6. `#include` directives are extracted and contribute to IMPORTS edges where target files exist in the indexed repository
7. UE5 macro extraction regex is tested and validated on real UE5 headers, including edge cases (multiline, nested parentheses)

**Plans:** TBD

---

### Phase 4: AngelScript Parser Implementation

**Goal:** Users can index UnrealAngel AngelScript files and see complete symbol graphs (functions, methods, classes) with UE5-style annotations captured.

**Depends on:** Phase 2 (binding available), Phase 3 (UE5 utilities and patterns established)

**Requirements:** INFRA-03, AS-01, AS-02, AS-03, AS-04

**Success Criteria** (what must be TRUE):
1. User can index a .as file and see functions, methods, and classes extracted as graph nodes
2. User can see EXTENDS edges from AngelScript class declarations to parent classes
3. UE5-style annotations in AngelScript (UCLASS, UFUNCTION equivalents, mixin markers) are extracted and stored in node `properties["ue_specifiers"]`
4. User can see IMPORTS edges from AngelScript import/include directives where target files exist in the indexed repository

**Plans:** TBD

---

### Phase 5: Dead-Code Exemptions & Unity Integration

**Goal:** False positive rates on Unity and UE5 codebases are eliminated by centralizing exemption logic for Blueprint exposure, UE5 base classes, and Unity lifecycle methods.

**Depends on:** Phase 1 (C# parser available), Phase 3 (UE5 utilities available)

**Requirements:** CS-05, CS-06, CPP-05, CPP-06

**Success Criteria** (what must be TRUE):
1. Functions/methods with BlueprintCallable, BlueprintEvent, BlueprintNativeEvent, or BlueprintPure specifiers are never flagged as dead code
2. UE5 framework base classes (AActor, UObject, UActorComponent, ACharacter, AGameMode, APlayerController, UWidget, etc.) are treated as known external types, not flagged as unknown or unresolved
3. C# Unity lifecycle methods (Start, Update, Awake, LateUpdate, FixedUpdate, OnDestroy, OnEnable, OnDisable, OnTriggerEnter, OnCollisionEnter, OnCollisionExit, OnTriggerExit, Reset, OnValidate, and equivalents) are never flagged as dead code
4. C# partial classes spread across multiple files are handled consistently without duplicating class nodes
5. Exemption logic is centralized in dead_code.py and ue5_utils.py, not scattered across parser implementations

**Plans:** TBD

---

### Phase 6: Module Nodes & Cross-Language Validation

**Goal:** Graph includes first-class MODULE nodes representing UE5 architectural units with DEPENDS_ON edges, and cross-language import/call resolution is validated on real multi-language projects.

**Depends on:** Phase 3 (C++ parser available), Phase 4 (AngelScript parser available)

**Requirements:** INFRA-04, MOD-01, MOD-02, MOD-03, MOD-04, MOD-05

**Success Criteria** (what must be TRUE):
1. NodeLabel.MODULE is added to model.py and a corresponding MODULE table exists in KuzuDB schema
2. RelType.DEPENDS_ON is added to model.py for module dependency edges
3. User can index a UE5 project with .Build.cs files and see MODULE nodes created with module names as properties
4. MODULE nodes are connected via DEPENDS_ON edges based on PublicDependencyModuleNames and PrivateDependencyModuleNames in .Build.cs files
5. Cross-language import resolution works correctly: IMPORTS edges exist between C#, C++, and AngelScript files; cross-file call graphs resolve correctly across all three languages
6. Integration tests pass on real multi-language UE5/C# projects, verifying import coherence and call tracing

**Plans:** TBD

---

## Progress

| Phase | Goal | Requirements | Status | Completed |
|-------|------|--------------|--------|-----------|
| 1. C# Parser Foundation | Parser pattern + symbol extraction | 1/3 | In Progress|  |
| 2. AngelScript Binding Spike | Binding research + validation | 1 | Not started | — |
| 3. UE5 C++ Parser & Macro Extraction | Macro extraction + parsing | 9 | Not started | — |
| 4. AngelScript Parser Implementation | Parser + UE5 annotations | 4 | Not started | — |
| 5. Dead-Code Exemptions & Unity Integration | Exemption logic + false-positive reduction | 4 | Not started | — |
| 6. Module Nodes & Cross-Language Validation | MODULE nodes + integration validation | 6 | Not started | — |

---

## Coverage

**Total v1 requirements:** 29
**Mapped:** 29/29 ✓

| Category | Count | Phases |
|----------|-------|--------|
| Infrastructure | 6 | 1, 2, 3, 4, 6 |
| C# Parser | 6 | 1, 5 |
| C++ Parser | 8 | 3, 5 |
| AngelScript Parser | 4 | 4 |
| Module Nodes | 5 | 6 |

---

## Key Dependencies

**Critical path:** Phase 1 → Phase 3 → Phase 5, Phase 6
- Phase 1 establishes parser pattern (unblocks Phase 3)
- Phase 3 UE5 utilities used by Phases 4 and 5
- Phase 2 runs in parallel (research spike)
- Phase 5 depends on Phases 1 and 3 for full exemption coverage
- Phase 6 validates all three parsers and module integration

**Safe parallel execution:**
- Phase 1 and Phase 2 can run in parallel
- Phase 4 can start as soon as Phase 2 completes and Phase 3 begins

---

*Last updated: 2026-03-23 (Phase 1 planned: 3 plans, 3 waves)*
