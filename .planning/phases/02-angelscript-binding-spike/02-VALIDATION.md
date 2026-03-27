---
phase: 2
slug: angelscript-binding-spike
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q -k "angelscript"` |
| **Full suite command** | `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q -k "angelscript"`
- **After every plan wave:** Run `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | INFRA-06 | integration | `uv run --with pytest python -m pytest tests/ -q -k "angelscript_binding"` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | INFRA-06 | integration | `uv run --with pytest python -m pytest tests/ -q -k "angelscript_parse"` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 2 | INFRA-06 | integration | `uv run --with pytest python -m pytest tests/ -q -k "angelscript_extract"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/test_angelscript_binding.py` — stubs for INFRA-06 binding import and parse
- [ ] Sample `.as` fixture file for parsing tests

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Grammar limitation documentation | INFRA-06 | Requires human review of parse tree quality | Read generated RESEARCH artifact and verify edge cases are enumerated |
| Fallback strategy decision | INFRA-06 | Architectural judgment call | Review RESEARCH.md section on fallback strategy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
