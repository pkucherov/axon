# Phase 1: C# Parser Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 01-c-parser-foundation
**Areas discussed:** Import resolution, Property node naming, Namespace qualification, SymbolInfo properties dict, Partial classes

---

## Import Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Best-effort namespace→path | Scan indexed .cs files for matching namespace declarations; emit IMPORTS edges; unresolved = no edge | ✓ |
| Extract but leave unresolved | Store using directives as ImportInfo with module=namespace; existing imports phase drops unmatched ones | |
| Skip IMPORTS edges for C# | Don't resolve at all; simplest Phase 1 | |

**User's choice:** Best-effort namespace→path

---

| Option | Description | Selected |
|--------|-------------|----------|
| Extract all three `using` forms, same strategy | Plain using, using static, using alias all extracted and resolved the same way | ✓ |
| Only plain `using` directives | Skip static and alias forms for simplicity | |
| You decide | Claude picks the approach | |

**User's choice:** Extract all three forms with the same strategy

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inside the C# parser (logic co-located) | Namespace resolution logic lives in csharp_lang.py, runs after all files parsed | ✓ |
| In imports.py post-processing | Parsers emit raw ImportInfo; imports.py gets a new C# resolution hook | |

**User's choice:** Logic co-located with C# parser module

---

## Property Node Naming

| Option | Description | Selected |
|--------|-------------|----------|
| One node per property, name=property name | 'MyProperty' as Method node; one conceptual unit | ✓ |
| One node per accessor | 'get_MyProperty' + 'set_MyProperty' as separate nodes; more granular | |
| You decide | Claude picks the approach | |

**User's choice:** One Method node per property, named by property name

---

## Namespace Qualification

| Option | Description | Selected |
|--------|-------------|----------|
| Simple names | 'MyActor', consistent with Python/TS | |
| Fully qualified names | 'Unreal.Core.MyActor', unique across project | |
| Qualified only on collision | Simple by default; qualify both when names collide | ✓ |

**User's choice:** Qualify only on collision

---

| Option | Description | Selected |
|--------|-------------|----------|
| At parse time, file-scoped (second pass in parser_phase.py) | Collision check runs after all files parsed; renames conflicting nodes | ✓ |
| Post-parse in imports.py phase | Simple names always emitted; dedupe step added to pipeline | |
| You decide | Claude handles implementation details | |

**User's choice:** Second pass in parser_phase.py after all files parsed

---

## SymbolInfo Properties Dict

| Option | Description | Selected |
|--------|-------------|----------|
| Add `properties: dict` in Phase 1 | Backward-compatible extension; C# attributes + future UE5 specifiers use it | ✓ |
| Add in Phase 3 | Smaller Phase 1 scope; base.py changed mid-milestone | |

**User's choice:** Add in Phase 1

---

| Option | Description | Selected |
|--------|-------------|----------|
| Store C# attributes in properties["cs_attributes"] | [Serializable], [DllImport], etc. extracted and stored | ✓ |
| Skip C# attributes in Phase 1 | Add in Phase 5 with dead-code exemption work | |
| You decide | Claude decides what to extract | |

**User's choice:** Store C# attributes in properties["cs_attributes"] in Phase 1

---

## Partial Classes

| Option | Description | Selected |
|--------|-------------|----------|
| One Class node per file | Duplicates accepted; Phase 5 merges; document limitation | ✓ |
| Suppress duplicates in Phase 1 | Cross-file awareness in parser; breaks single-file parse contract | |

**User's choice:** One Class node per file (duplicates accepted as Phase 1 baseline)

---

## Claude's Discretion

- Exact tree-sitter node type names for the C# grammar
- Content of `_BUILTIN_TYPES` frozenset for C#
- Whether nested types are extracted or skipped
- Signature string format for C# methods

## Deferred Ideas

- Unity lifecycle method exemptions → Phase 5
- Partial class merging → Phase 5
- Unity attribute handling for dead-code → Phase 5
