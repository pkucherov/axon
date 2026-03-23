---
phase: 1
slug: c-parser-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.0.0 with pytest-asyncio >= 0.24.0 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py -q` |
| **Full suite command** | `uv run --with pytest --with pytest-asyncio python -m pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (quick), ~120 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py -q`
- **After every plan wave:** Run `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| — | — | W0 | INFRA-01 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestRegistration -x` | ❌ Wave 0 | ⬜ pending |
| — | — | W0 | INFRA-05 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestImport -x` | ❌ Wave 0 | ⬜ pending |
| — | — | W0 | CS-01 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestSymbolExtraction -x` | ❌ Wave 0 | ⬜ pending |
| — | — | W0 | CS-02 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestImportResolution -x` | ❌ Wave 0 | ⬜ pending |
| — | — | W0 | CS-03 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestHeritage -x` | ❌ Wave 0 | ⬜ pending |
| — | — | W0 | CS-04 | unit | `uv run --with pytest --with pytest-asyncio python -m pytest tests/core/test_parser_csharp.py::TestProperties -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/test_parser_csharp.py` — test stubs for INFRA-01, INFRA-05, CS-01, CS-02, CS-03, CS-04

*Existing infrastructure covers all other needs (pytest already installed, pyproject.toml configured).*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
