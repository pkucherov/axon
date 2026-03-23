# Comparison: AngelScript Tree-Sitter Grammars

**Context:** Five community tree-sitter grammars exist for AngelScript. Need to choose one for v1 that best supports UnrealEngine integration.

**Recommendation:** `dimitrijejankov/tree-sitter-unreal-angelscript` (best odds of UE5 support; needs validation)

---

## Candidate Grammars

| Repository | Language | Stars | Last Commit | UE-Aware? | Notes |
|------------|----------|-------|-------------|-----------|-------|
| **dimitrijejankov/tree-sitter-unreal-angelscript** | C | N/A | Recent | ✓ LIKELY | Explicit Unreal in name; appears most UE5-focused |
| **dehorsley/tree-sitter-angelscript** | JavaScript | 3 | Recent | ? Unknown | Generic AS; no UE indication |
| **Relrin/tree-sitter-angelscript** | C | N/A | 2023 | ? Unknown | Has unreal-engine tag; less recent |
| **amerikrainian/tree-sitter-angelscript** | JavaScript | 1 | Old | ✗ No | Minimal activity; likely vanilla AS only |
| **WarRaft/tree-sitter-as** | C | N/A | Unknown | ? Unknown | Limited info; not recommended without review |

---

## Quick Comparison

### dimitrijejankov/tree-sitter-unreal-angelscript

**Strengths:**
- ✓ Name explicitly targets Unreal; likely designed for UnrealAngel dialect
- ✓ C-based (compiled; faster parsing than JavaScript)
- ✓ Appears active/recent

**Weaknesses:**
- ? UE5 support unverified; needs code inspection
- ? Macro handling unclear (does it support UCLASS/UFUNCTION equivalents?)
- ? Documentation sparse or absent

**Recommendation:** **PRIMARY CHOICE** — inspect grammar.js and test on 3-5 real UnrealAngel files before Phase 1

---

### dehorsley/tree-sitter-angelscript

**Strengths:**
- ✓ Generic AS parser; should handle core language
- ✓ JavaScript implementation (easy to inspect and debug)

**Weaknesses:**
- ✗ No UE5 awareness; macro support unlikely
- ~ Requires decorator extraction fallback if UE macros present

**Recommendation:** **SECONDARY CHOICE** — if dimitrijejankov doesn't work

---

### Relrin/tree-sitter-angelscript

**Strengths:**
- ✓ Unreal-engine topic tag suggests some UE awareness

**Weaknesses:**
- ✗ Less recent than dimitrijejankov
- ? Documentation absent; would require code inspection

**Recommendation:** **TERTIARY CHOICE** — only if dimitrijejankov and dehorsley fail

---

## Decision Matrix

| Criterion | dimitrijejankov | dehorsley | Relrin |
|-----------|-----------------|-----------|--------|
| **UE5 Focus** | ✓✓ | ✗ | ✓ |
| **Likely Maintained** | ✓ | ✓ | ~ |
| **Performance** | ✓ C | ~ JS | ✓ C |
| **Macro Support** | ? Unknown | ✗ Unlikely | ? Unknown |
| **Documentation** | ✗ Sparse | ~ Some | ✗ Sparse |
| **Ease of Debug** | ~ C | ✓ JS | ~ C |
| **Risk Level** | LOW | MEDIUM | MEDIUM |

---

## Validation Protocol

### Before Phase 1

1. **Clone dimitrijejankov repository**
   ```bash
   git clone https://github.com/dimitrijejankov/tree-sitter-unreal-angelscript.git
   cd tree-sitter-unreal-angelscript
   ```

2. **Inspect grammar.js**
   - Does grammar define `function_declaration`, `class_declaration`, `method_declaration`?
   - Are there rules for UCLASS, UFUNCTION equivalents?
   - How are imports/includes handled?

3. **Get real UnrealAngel code samples**
   - Find ~3-5 .as files from a real UnrealEngine/AngelScript project
   - Can be from Hazelight, Epic's samples, or community projects

4. **Parse samples with tree-sitter-cli**
   ```bash
   npm install -g tree-sitter-cli
   tree-sitter parse sample.as
   ```
   - Check: Do symbols extract correctly?
   - Check: Are class/method/function nodes present?

5. **Document findings**
   - What node types are available?
   - Can decorators/macros be extracted?
   - Are there limitations or surprises?

### Fallback Decision

If dimitrijejankov fails:
- Use dehorsley as fallback (vanilla AS support is better than nothing)
- Implement manual macro detection in parser (regex on raw source)
- Document assumption: "UnrealAngel dialect not optimized; macro extraction may be fragile"

If both fail:
- Implement custom AngelScript parser using tree-sitter-based pattern matching
- Or: Defer AngelScript to Phase 2 (lower priority than C# and C++)

---

## Recommendation

**Choose: dimitrijejankov/tree-sitter-unreal-angelscript**

**Action:** Before Phase 1 kickoff, validate it against real code (4-6 hours). If validation succeeds, integrate as dependency. If validation fails, fall back to dehorsley.

**Risk:** LOW (validation is fast; fallback is available)

**Timeline Impact:** 4-6 hours validation; does not block other work

