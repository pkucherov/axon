# Phase 2: AngelScript Binding Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 02-angelscript-binding-spike
**Areas discussed:** Binding mechanism, Grammar source & viability, Distribution strategy, Spike success criteria

---

## Binding Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| ctypes wrapper | Compile grammar.c → .so/.dll via build script; load at runtime with ctypes | |
| Vendored binary artifact | Pre-compiled binaries checked into repo under vendor/ | |
| Regex-based fallback | Skip tree-sitter entirely; write regex/line-scanning parser | |
| Build wheel from source | Fork grammar, add pyproject.toml, build proper Python wheel | ✓ |

**User's choice:** Build a proper Python wheel from vendored grammar source using a local path dependency.

**Notes:** User specified using the Hazelight VS Code extension (`Hazelight/vscode-unreal-angelscript`) as the source of truth for UnrealAngel syntax. Hazelight uses PEGGY (PEG.js successor), not tree-sitter — its grammar.js serves as the reference spec. User also called out `dimitrijejankov/tree-sitter-unreal-angelscript` as an additional candidate to investigate. "Cleanest long-term solution" was the stated priority; no PyPI publishing required.

---

## Grammar Source & Viability

| Option | Description | Selected |
|--------|-------------|----------|
| dimitrijejankov first | UE5-specific grammar; evaluate as primary candidate | |
| Relrin first | Generic AngelScript grammar; evaluate as primary candidate | |
| Evaluate both, pick best | Test both against sample .as files; pick better coverage | ✓ |

**User's choice:** Evaluate both grammars, pick the one with better UE5/UnrealAngel construct coverage.

**Notes:** Fallback if neither grammar has sufficient coverage: fork and extend the better grammar using Hazelight PEGGY grammar as the reference spec (not regex fallback, not deferral).

---

## Distribution Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| vendor/ at repo root | Standard vendor/ convention with path dep in pyproject.toml | |
| src/axon/core/parsers/vendor/ | Co-located with parser code | |
| third-party/ at repo root | Alternative conventional path | ✓ |

**User's choice:** `third-party/` at repo root. Path dependency in pyproject.toml:
```
"tree-sitter-angelscript @ file:./third-party/tree-sitter-angelscript"
```

---

## Spike Success Criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Full UnrealAngel coverage | Functions, methods, classes, inheritance, UE5 annotations, includes | ✓ |
| Structural coverage only | Functions, methods, classes, inheritance — annotations via regex | |
| Minimal: syntax tree only | Just produces a parse tree without errors | |

**User's choice:** Full UnrealAngel coverage — all four construct categories must parse.

---

## Fallback Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Regex parser | Write regex-based parser if grammar insufficient | |
| Extend the better grammar | Fork and extend grammar.js using Hazelight as reference | ✓ |
| Defer Phase 4 | Skip AngelScript in v1 | |

**User's choice:** Extend the better grammar. If coverage gaps exist after evaluation, extend grammar.js using Hazelight PEGGY parser as the spec. No regex fallback.

---

## Claude's Discretion

- Which specific grammar (Relrin vs dimitrijejankov) is ultimately selected — determined by spike results
- Exact Python package name in pyproject.toml
- Grammar extension scope (which rules to patch)
- Spike test sample file content

## Deferred Ideas

- AngelScript parser implementation — Phase 4
- PyPI publishing of the AngelScript wheel — post-v1
