# PIT Runner Scripts — Implementation Plan (simple)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Two convenience CLIs:
1. `scripts/run_pipeline.py` — run **convert then import** from ONE combined config; convert's `output_path` is auto-fed as import's `rics_path`, and convert's date is shared to import's `base_date`.
2. `scripts/run_import.py` — run **import only** from one standalone import config.

**Architecture:** Both scripts are thin orchestrators over the already-tested CLI internals — `pit.converter.cli.run_converter_with_config(dict)` and `pit.importer.cli.run_import_with_config(dict)` (each sets up logging, resolves paths, runs `pipeline.run`, writes its results JSON, returns 0/1). No new pipeline logic; no Python backend changes.

**Tech Stack:** Python 3.11 (project venv, pandas 2.x), PyYAML, pytest. Windows.

## Global Constraints

- Combined config is one YAML with two top-level sections, each mirroring the existing configs exactly:
  ```yaml
  convert: { <same keys as configs/convert.example.yaml> }
  import:  { <same keys as the importer config, MINUS rics_path and base_date> }
  ```
- **Auto-links (script-applied, override anything in the file):**
  - `import.paths.rics_path` = `convert.converter_paths.output_path`
  - `import.settings.base_date` = `convert.start_date` reformatted `YYYYMMDD` → `YYYY-MM-DD`
- Import runs ONLY if convert returns 0; otherwise stop and report.
- Reuse `run_converter_with_config` / `run_import_with_config` verbatim (they own results JSON + logging). Scripts return the final exit code (0 success, non-zero failure).
- Run with the project venv: `.\.venv\Scripts\python scripts\<name>.py <config.yaml>`.

---

### Task 1: `run_pipeline.py` (convert + import) + example config

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `configs/pipeline.example.yaml`
- Test: `tests/scripts/__init__.py`, `tests/scripts/test_run_pipeline.py`

**Interfaces:**
- `run_pipeline.reformat_date(yyyymmdd: str) -> str` — `"20250630"` → `"2025-06-30"`; if already `YYYY-MM-DD`, return unchanged.
- `run_pipeline.run(combined: dict) -> int` — runs convert, links rics_path + base_date, runs import; returns final exit code (import's rc, or convert's rc if convert failed).
- `run_pipeline.main(argv=None) -> int` — parse config path, load YAML, validate `convert`/`import` keys, call `run`.

- [ ] **Step 1: Write the failing test** (mocks the two heavy CLI calls; asserts orchestration + links)

```python
# tests/scripts/test_run_pipeline.py
import os, sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import scripts.run_pipeline as rp


def test_reformat_date():
    assert rp.reformat_date("20250630") == "2025-06-30"
    assert rp.reformat_date("2025-06-30") == "2025-06-30"


def test_run_links_output_and_date_then_imports(monkeypatch):
    calls = {}
    monkeypatch.setattr(rp.converter_cli, "run_converter_with_config",
                        lambda cfg: calls.setdefault("convert", cfg) or 0)
    monkeypatch.setattr(rp.importer_cli, "run_import_with_config",
                        lambda cfg: calls.setdefault("import", cfg) or 0)
    combined = {
        "convert": {"start_date": "20251231", "converter_paths": {"output_path": "C:/out/rics"}},
        "import": {"paths": {}, "settings": {}},
    }
    rc = rp.run(combined)
    assert rc == 0
    assert calls["import"]["paths"]["rics_path"] == "C:/out/rics"     # auto-linked
    assert calls["import"]["settings"]["base_date"] == "2025-12-31"   # shared date


def test_import_skipped_when_convert_fails(monkeypatch):
    monkeypatch.setattr(rp.converter_cli, "run_converter_with_config", lambda cfg: 1)
    ran = {"import": False}
    monkeypatch.setattr(rp.importer_cli, "run_import_with_config",
                        lambda cfg: ran.__setitem__("import", True) or 0)
    rc = rp.run({"convert": {"start_date": "20250630", "converter_paths": {"output_path": "x"}},
                 "import": {"paths": {}, "settings": {}}})
    assert rc == 1 and ran["import"] is False
```

- [ ] **Step 2: Run → fails** (`.\.venv\Scripts\python -m pytest tests/scripts/test_run_pipeline.py -v`, module missing).

- [ ] **Step 3: Implement `run_pipeline.py`**

```python
#!/usr/bin/env python
"""Run convert then import from one combined config.

Usage (project venv):  .\\.venv\\Scripts\\python scripts\\run_pipeline.py <config.yaml>

The config has two sections, `convert:` and `import:`. The convert stage's
output folder is auto-fed as the import stage's rics_path, and the convert
date is shared to import base_date. Import runs only if convert succeeds.
"""
from __future__ import annotations
import os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import yaml
from pit.converter import cli as converter_cli
from pit.importer import cli as importer_cli


def reformat_date(d: str) -> str:
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def run(combined: dict) -> int:
    convert_cfg = combined["convert"]
    import_cfg = combined["import"]

    print("=== Stage 1/2: Convert ===")
    rc = converter_cli.run_converter_with_config(convert_cfg)
    if rc != 0:
        print(f"Convert failed (exit {rc}); skipping import.", file=sys.stderr)
        return rc

    # Auto-link: import reads the convert output; share the date.
    import_cfg.setdefault("paths", {})["rics_path"] = convert_cfg["converter_paths"]["output_path"]
    import_cfg.setdefault("settings", {})["base_date"] = reformat_date(convert_cfg["start_date"])

    print("=== Stage 2/2: Import ===")
    return importer_cli.run_import_with_config(import_cfg)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Usage: run_pipeline.py <combined_config.yaml>", file=sys.stderr)
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"Config not found: {path}", file=sys.stderr)
        return 2
    with open(path, "r", encoding="utf-8") as f:
        combined = yaml.safe_load(f)
    if not isinstance(combined, dict) or "convert" not in combined or "import" not in combined:
        print("Config must contain top-level 'convert:' and 'import:' sections.", file=sys.stderr)
        return 2
    return run(combined)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create `configs/pipeline.example.yaml`** — `convert:` block = the body of `configs/convert.example.yaml`; `import:` block = the importer config MINUS `rics_path` and `base_date` (with a comment noting they're auto-set). Add `tests/scripts/__init__.py` (empty).

- [ ] **Step 5: Run → passes** (`-m pytest tests/scripts/test_run_pipeline.py -v` → 3 passed) and full suite green.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_pipeline.py configs/pipeline.example.yaml tests/scripts/
git commit -m "feat(scripts): run_pipeline.py — convert+import from one combined config"
```

---

### Task 2: `run_import.py` (import only)

**Files:**
- Create: `scripts/run_import.py`
- Test: `tests/scripts/test_run_import.py`

**Interfaces:**
- `run_import.main(argv=None) -> int` — thin wrapper: delegates to `pit.importer.cli.main` (which already loads a standalone import YAML, runs the importer, writes results, returns 0/1).

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_run_import.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import scripts.run_import as ri


def test_delegates_to_importer_cli(monkeypatch):
    seen = {}
    monkeypatch.setattr(ri.importer_cli, "main", lambda argv: seen.setdefault("argv", argv) or 0)
    rc = ri.main(["some_import.yaml"])
    assert rc == 0 and seen["argv"] == ["some_import.yaml"]


def test_missing_arg_returns_2(capsys):
    assert ri.main([]) == 2
```

- [ ] **Step 2: Run → fails.**

- [ ] **Step 3: Implement `run_import.py`**

```python
#!/usr/bin/env python
"""Run import only, from one standalone import config.

Usage (project venv):  .\\.venv\\Scripts\\python scripts\\run_import.py <import_config.yaml>

Thin wrapper over the importer CLI: the config points rics_path at already-
produced RICS format data (e.g. a prior convert run's output).
"""
from __future__ import annotations
import os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pit.importer import cli as importer_cli


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Usage: run_import.py <import_config.yaml>", file=sys.stderr)
        return 2
    return importer_cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run → passes; full suite green.**

- [ ] **Step 5: Commit**

```bash
git add scripts/run_import.py tests/scripts/test_run_import.py
git commit -m "feat(scripts): run_import.py — import-only from one config"
```

---

## Self-Review

- **Coverage:** run_pipeline links output→rics_path and shares the date (Task 1); import-only wrapper (Task 2). Both reuse tested CLI internals — no new pipeline logic.
- **No placeholders:** full code in every step; `configs/pipeline.example.yaml` content specified by reference to existing configs (Step 4 will inline the actual blocks).
- **Types:** `run(combined)`, `reformat_date`, `main` consistent between impl and tests; `converter_cli.run_converter_with_config` / `importer_cli.run_import_with_config` / `importer_cli.main` are the real, existing signatures.
- **Testable without SG:** tests monkeypatch the two heavy calls, so no Excel/SG needed; gated suite stays green.
- **Note:** results JSON/logs for each stage land next to their respective `pit/*/cli.py` (existing behavior), so the pipeline produces both `rics_converter_results.json` and `rics_import_results.json`.
