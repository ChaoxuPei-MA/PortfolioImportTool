# PIT Foundation & Golden-Master Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `PortfolioImportTool` Python package skeleton, the shared core
(`pit/shared/`: results contract, config loader/validator, logging), and a golden-master
capture/compare harness — the anti-regression baseline every later refactor is checked
against.

**Architecture:** A single installable package `pit` with a `shared/` subpackage that both
the (later) converter and importer reuse. The shared core is pure, dependency-light, and
fully unit-tested. The golden-master harness runs the *original* tools against local sample
data (never committed) and snapshots their output, so Parts 2–3 can prove byte-for-byte
equivalence after refactoring.

**Tech Stack:** Python 3.11+, PyYAML, pytest. No new heavy dependencies. Windows.

## Global Constraints

- Python package name is `pit`; package is `pip install -e .` installable.
- No data committed to git — `tests/fixtures/`, `tests/golden/`, and any sample data are gitignored.
- Results JSON schema (union of both tools): keys `status, message, timestamp, output_path, log_file, summary_file`. `status` is `"success"` or `"error"`. `summary_file` is optional (Converter sets it, Importer leaves it `None`).
- Each tool writes its own results filename — never a shared file. The writer takes the filename as a parameter.
- The two tools are fully decoupled: no shared runtime state, no import-time side effects.
- Tool name "Portfolio Import Tool"; `PIT_` prefix for user-facing artifacts.
- Match existing logging format exactly: `%(asctime)s - %(levelname)s - %(message)s`, file handler `mode='w'`.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `pit/__init__.py`
- Create: `pit/version.py`
- Create: `pit/shared/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/shared/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `pit`; `pit.version.__version__` (str).

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
import pit
from pit.version import __version__


def test_package_imports():
    assert pit is not None


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__  # non-empty
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pit'`

- [ ] **Step 3: Create the package files**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pit"
version = "0.1.0"
description = "Portfolio Import Tool — convert client data to RICS files and import into Moody's SG"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "pandas>=2.0", "openpyxl>=3.1"]

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[project.scripts]
pit-convert = "pit.converter.cli:main"
pit-import = "pit.importer.cli:main"

[tool.setuptools.packages.find]
include = ["pit*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```gitignore
# .gitignore
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
build/
dist/
*.spec.bak

# Never commit data or generated baselines
tests/fixtures/
tests/golden/
sample_data/
excelTool/*.xlsm

# Local results/logs
*.log
rics_*_results.json
temp_config*.yaml
*_debug.txt
```

```python
# pit/version.py
__version__ = "0.1.0"
```

```python
# pit/__init__.py
from pit.version import __version__

__all__ = ["__version__"]
```

```python
# pit/shared/__init__.py
```

```python
# tests/__init__.py
```

```python
# tests/shared/__init__.py
```

- [ ] **Step 4: Install editable and run the test**

Run: `python -m pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore pit/ tests/
git commit -m "feat: scaffold pit package with smoke test"
```

---

### Task 2: Shared results contract (`pit/shared/results.py`)

**Files:**
- Create: `pit/shared/results.py`
- Test: `tests/shared/test_results.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Result` dataclass with fields `status: str`, `message: str`, `timestamp: str`, `output_path: Optional[str] = None`, `log_file: Optional[str] = None`, `summary_file: Optional[str] = None`.
  - `Result.success(message, *, output_path=None, summary_file=None, log_file=None) -> Result` (classmethod; sets `status="success"`, fills `timestamp`).
  - `Result.error(message, *, log_file=None) -> Result` (classmethod; sets `status="error"`, fills `timestamp`).
  - `Result.to_dict() -> dict` (keys in the fixed order above).
  - `write_results(result: Result, out_dir: str, filename: str) -> str` — prints `json.dumps(result.to_dict())` to stdout, writes pretty JSON to `os.path.join(out_dir, filename)`, returns the file path. Never raises on write failure (logs and continues).

- [ ] **Step 1: Write the failing tests**

```python
# tests/shared/test_results.py
import json
import os

from pit.shared.results import Result, write_results


def test_success_has_status_and_timestamp():
    r = Result.success("done", output_path="C:/out", summary_file="C:/out/summary.txt")
    d = r.to_dict()
    assert d["status"] == "success"
    assert d["message"] == "done"
    assert d["output_path"] == "C:/out"
    assert d["summary_file"] == "C:/out/summary.txt"
    assert d["timestamp"]  # non-empty ISO string


def test_error_omits_optional_paths():
    r = Result.error("boom", log_file="C:/x.log")
    d = r.to_dict()
    assert d["status"] == "error"
    assert d["message"] == "boom"
    assert d["log_file"] == "C:/x.log"
    assert d["output_path"] is None
    assert d["summary_file"] is None


def test_to_dict_key_order_is_fixed():
    r = Result.success("ok")
    assert list(r.to_dict().keys()) == [
        "status", "message", "timestamp", "output_path", "log_file", "summary_file",
    ]


def test_write_results_writes_named_file(tmp_path):
    r = Result.success("ok", output_path=str(tmp_path))
    path = write_results(r, str(tmp_path), "rics_converter_results.json")
    assert path == os.path.join(str(tmp_path), "rics_converter_results.json")
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["status"] == "success"


def test_write_results_never_raises_on_bad_dir():
    r = Result.error("x")
    # Non-existent nested dir that we don't create — must not raise.
    path = write_results(r, "Z:/no/such/dir/(probably)", "rics_import_results.json")
    assert path  # returns the intended path even if write failed
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/shared/test_results.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pit.shared.results'`

- [ ] **Step 3: Implement `results.py`**

```python
# pit/shared/results.py
"""Single results-JSON contract shared by the Convert and Import tools.

Both tools emit the same schema, but each writes its OWN file (passed as
`filename`) — they never share a results file. This keeps the two tools
fully decoupled.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_KEY_ORDER = ["status", "message", "timestamp", "output_path", "log_file", "summary_file"]


@dataclass
class Result:
    status: str
    message: str
    timestamp: str
    output_path: Optional[str] = None
    log_file: Optional[str] = None
    summary_file: Optional[str] = None

    @classmethod
    def success(cls, message: str, *, output_path: Optional[str] = None,
                summary_file: Optional[str] = None, log_file: Optional[str] = None) -> "Result":
        return cls(
            status="success",
            message=message,
            timestamp=datetime.now().isoformat(),
            output_path=output_path,
            log_file=log_file,
            summary_file=summary_file,
        )

    @classmethod
    def error(cls, message: str, *, log_file: Optional[str] = None) -> "Result":
        return cls(
            status="error",
            message=message,
            timestamp=datetime.now().isoformat(),
            log_file=log_file,
        )

    def to_dict(self) -> dict:
        return {key: getattr(self, key) for key in _KEY_ORDER}


def write_results(result: Result, out_dir: str, filename: str) -> str:
    """Print JSON to stdout (for Excel capture) and write it to out_dir/filename.

    Returns the intended file path. Never raises — a write failure is logged.
    """
    payload = result.to_dict()
    print(json.dumps(payload))

    path = os.path.join(out_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:  # non-critical: Excel also reads stdout
        logger.error("Failed to write results JSON to %s: %s", path, exc)
    return path
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/shared/test_results.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add pit/shared/results.py tests/shared/test_results.py
git commit -m "feat: shared results-JSON contract"
```

---

### Task 3: Shared config loader + validator (`pit/shared/config.py`)

**Files:**
- Create: `pit/shared/config.py`
- Test: `tests/shared/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ConfigError(Exception)` — raised with a human-readable message.
  - `load_config(path: str) -> dict` — reads YAML; raises `ConfigError` with a clear message on missing file or YAML syntax error.
  - `require(config: dict, dotted_keys: list[str]) -> None` — validates that each dotted key path (e.g. `"converter_paths.output_path"`) exists and is non-empty; raises `ConfigError` listing every missing/empty key at once.
  - `get(config: dict, dotted_key: str, default=None)` — safe nested lookup.

- [ ] **Step 1: Write the failing tests**

```python
# tests/shared/test_config.py
import pytest

from pit.shared.config import ConfigError, load_config, require, get


def test_load_missing_file_raises_configerror():
    with pytest.raises(ConfigError) as exc:
        load_config("Z:/does/not/exist.yaml")
    assert "not found" in str(exc.value).lower()


def test_load_bad_yaml_raises_configerror(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("key: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(str(p))
    assert "yaml" in str(exc.value).lower()


def test_load_valid_yaml_returns_dict(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text("a: 1\nb:\n  c: hello\n", encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg == {"a": 1, "b": {"c": "hello"}}


def test_require_reports_all_missing_keys():
    cfg = {"converter_paths": {"output_path": "", "data_path": "C:/d"}}
    with pytest.raises(ConfigError) as exc:
        require(cfg, ["converter_paths.output_path", "start_date"])
    msg = str(exc.value)
    assert "converter_paths.output_path" in msg
    assert "start_date" in msg


def test_require_passes_when_all_present():
    cfg = {"start_date": "20250630", "converter_paths": {"output_path": "C:/o"}}
    require(cfg, ["start_date", "converter_paths.output_path"])  # no raise


def test_get_nested_with_default():
    cfg = {"a": {"b": 2}}
    assert get(cfg, "a.b") == 2
    assert get(cfg, "a.z", "fallback") == "fallback"
    assert get(cfg, "missing.path", None) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/shared/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pit.shared.config'`

- [ ] **Step 3: Implement `config.py`**

```python
# pit/shared/config.py
"""YAML config loading and validation shared by both tools.

Raises ConfigError with actionable messages instead of leaking KeyError /
yaml internals to the user.
"""
from __future__ import annotations

import os
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or incomplete."""


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parsing error in {path}: {exc}") from exc
    if data is None:
        raise ConfigError(f"Config file is empty: {path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}: {path}")
    return data


def get(config: dict, dotted_key: str, default: Any = None) -> Any:
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def require(config: dict, dotted_keys: list[str]) -> None:
    missing = []
    for key in dotted_keys:
        value = get(config, key, _MISSING)
        if value is _MISSING or value == "" or value is None:
            missing.append(key)
    if missing:
        raise ConfigError(
            "Missing or empty required config keys:\n"
            + "\n".join(f"  - {k}" for k in missing)
        )


_MISSING = object()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/shared/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add pit/shared/config.py tests/shared/test_config.py
git commit -m "feat: shared config loader with clear validation errors"
```

---

### Task 4: Shared logging setup (`pit/shared/logging_setup.py`)

**Files:**
- Create: `pit/shared/logging_setup.py`
- Test: `tests/shared/test_logging_setup.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `setup_logging(log_path: str) -> str` — configures root logging with a `FileHandler(log_path, mode="w")` plus a stdout `StreamHandler`, format `%(asctime)s - %(levelname)s - %(message)s`, level INFO. Returns `log_path`. Idempotent: clears existing handlers first so repeated calls in one process don't double-log.

- [ ] **Step 1: Write the failing tests**

```python
# tests/shared/test_logging_setup.py
import logging
import os

from pit.shared.logging_setup import setup_logging


def test_setup_creates_log_file_and_writes(tmp_path):
    log_path = str(tmp_path / "pit.log")
    returned = setup_logging(log_path)
    assert returned == log_path
    logging.getLogger("x").info("hello-line")
    logging.shutdown()
    assert os.path.exists(log_path)
    with open(log_path, encoding="utf-8") as f:
        content = f.read()
    assert "hello-line" in content
    assert " - INFO - " in content


def test_setup_is_idempotent_no_duplicate_handlers(tmp_path):
    log_path = str(tmp_path / "pit.log")
    setup_logging(log_path)
    setup_logging(log_path)
    file_handlers = [h for h in logging.getLogger().handlers
                     if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/shared/test_logging_setup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pit.shared.logging_setup'`

- [ ] **Step 3: Implement `logging_setup.py`**

```python
# pit/shared/logging_setup.py
"""Centralized logging configuration for both tools."""
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def setup_logging(log_path: str) -> str:
    root = logging.getLogger()
    # Idempotent: remove handlers from any prior setup in this process.
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(_FORMAT)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return log_path
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/shared/test_logging_setup.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pit/shared/logging_setup.py tests/shared/test_logging_setup.py
git commit -m "feat: shared logging setup"
```

---

### Task 5: Golden-master harness (capture + compare)

**Purpose:** Freeze the *current* behavior of the original tools so Parts 2–3 can prove the
refactor changed nothing. Uses local sample data referenced by an env var — **never
committed**. Output snapshots land in gitignored `tests/golden/`.

**Files:**
- Create: `tests/golden_master/__init__.py`
- Create: `tests/golden_master/tree_hash.py`
- Create: `tests/golden_master/capture_converter.py`
- Create: `tests/golden_master/README.md`
- Test: `tests/golden_master/test_tree_hash.py`

**Interfaces:**
- Consumes: `pit` (none directly); the original Converter at a path given by env var `PIT_ORIG_CONVERTER` and sample data at `PIT_SAMPLE_DATA`.
- Produces:
  - `tree_hash.hash_tree(root: str) -> dict[str, str]` — maps each file's relative POSIX path (sorted) to its SHA-256 hex digest, for every file under `root`. Deterministic; ignores nothing (caller points it at the output tree only).
  - `tree_hash.write_manifest(root: str, manifest_path: str) -> dict` — writes the mapping as pretty JSON and returns it.
  - `tree_hash.diff_manifests(a: dict, b: dict) -> list[str]` — returns human-readable difference lines (added / removed / changed). Empty list == identical.

- [ ] **Step 1: Write the failing tests for the hashing core**

```python
# tests/golden_master/test_tree_hash.py
import json

from tests.golden_master.tree_hash import hash_tree, write_manifest, diff_manifests


def _make_tree(base):
    (base / "sub").mkdir()
    (base / "a.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (base / "sub" / "b.csv").write_text("p\n9\n", encoding="utf-8")


def test_hash_tree_is_deterministic_and_relative(tmp_path):
    _make_tree(tmp_path)
    h1 = hash_tree(str(tmp_path))
    h2 = hash_tree(str(tmp_path))
    assert h1 == h2
    assert set(h1.keys()) == {"a.csv", "sub/b.csv"}


def test_changed_file_changes_hash(tmp_path):
    _make_tree(tmp_path)
    before = hash_tree(str(tmp_path))
    (tmp_path / "a.csv").write_text("x,y\n1,3\n", encoding="utf-8")
    after = hash_tree(str(tmp_path))
    assert before["a.csv"] != after["a.csv"]
    assert before["sub/b.csv"] == after["sub/b.csv"]


def test_diff_manifests_reports_changes():
    a = {"f1": "h1", "f2": "h2", "f3": "h3"}
    b = {"f1": "h1", "f2": "CHANGED", "f4": "h4"}
    lines = diff_manifests(a, b)
    joined = "\n".join(lines)
    assert "f2" in joined          # changed
    assert "f3" in joined          # removed
    assert "f4" in joined          # added
    assert "f1" not in joined      # unchanged not reported


def test_write_manifest_roundtrip(tmp_path):
    _make_tree(tmp_path)
    out = tmp_path / "manifest.json"
    manifest = write_manifest(str(tmp_path), str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == manifest
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/golden_master/test_tree_hash.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.golden_master.tree_hash'`

- [ ] **Step 3: Implement the hashing core and package marker**

```python
# tests/golden_master/__init__.py
```

```python
# tests/golden_master/tree_hash.py
"""Deterministic file-tree hashing for golden-master comparison."""
from __future__ import annotations

import hashlib
import json
import os


def hash_tree(root: str) -> dict:
    result: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            result[rel] = h.hexdigest()
    return dict(sorted(result.items()))


def write_manifest(root: str, manifest_path: str) -> dict:
    manifest = hash_tree(root)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def diff_manifests(a: dict, b: dict) -> list:
    lines: list[str] = []
    for key in sorted(set(a) | set(b)):
        if key not in b:
            lines.append(f"REMOVED: {key}")
        elif key not in a:
            lines.append(f"ADDED:   {key}")
        elif a[key] != b[key]:
            lines.append(f"CHANGED: {key}")
    return lines
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/golden_master/test_tree_hash.py -v`
Expected: 4 passed

- [ ] **Step 5: Write the converter capture script (no test — it drives the original tool)**

```python
# tests/golden_master/capture_converter.py
"""Capture a golden-master manifest of the ORIGINAL converter's output.

Usage (PowerShell), pointing at the existing original project + local sample data:

    $env:PIT_ORIG_CONVERTER = "C:\\...\\Projects\\RICS_BulkImportFiles_Converter"
    $env:PIT_SAMPLE_DATA    = "C:\\...\\some\\local\\UserData_parent_with_config"
    python tests/golden_master/capture_converter.py C:\\tmp\\pit_gm\\convert

The script runs the original converter via its config, then writes
tests/golden/converter_manifest.json (gitignored) from the produced output tree.

This script is intentionally thin: it shells out to the original tool exactly as
the original Excel wrapper does, so the captured behavior is the real baseline.
"""
from __future__ import annotations

import os
import subprocess
import sys

from tests.golden_master.tree_hash import write_manifest

GOLDEN_DIR = os.path.join("tests", "golden")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: capture_converter.py <output_tree_dir>", file=sys.stderr)
        return 2
    output_tree = argv[1]

    orig = os.environ.get("PIT_ORIG_CONVERTER")
    if not orig:
        print("Set PIT_ORIG_CONVERTER to the original converter project dir.", file=sys.stderr)
        return 2

    config_path = os.environ.get("PIT_CONVERTER_CONFIG", os.path.join(orig, "config.yaml"))
    if not os.path.exists(config_path):
        print(f"Converter config not found: {config_path}", file=sys.stderr)
        return 2

    # Run the original converter in its own directory (matches wrapper behavior).
    env = dict(os.environ, RICS_CONFIG_PATH=config_path)
    print(f"Running original converter: {orig} with {config_path}")
    proc = subprocess.run(
        [sys.executable, "main.py"], cwd=orig, env=env,
        capture_output=True, text=True,
    )
    print(proc.stdout[-2000:])
    if proc.returncode != 0:
        print(proc.stderr[-4000:], file=sys.stderr)
        print("Original converter run FAILED — cannot capture baseline.", file=sys.stderr)
        return 1

    if not os.path.isdir(output_tree):
        print(f"Expected output tree not found: {output_tree}\n"
              f"Point this script at the converter's output_path/<start_date> folder.",
              file=sys.stderr)
        return 1

    os.makedirs(GOLDEN_DIR, exist_ok=True)
    manifest_path = os.path.join(GOLDEN_DIR, "converter_manifest.json")
    manifest = write_manifest(output_tree, manifest_path)
    print(f"Wrote {manifest_path} with {len(manifest)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 6: Write the harness README**

```markdown
# tests/golden_master/README.md

Golden-master baselines freeze the ORIGINAL tools' output before refactoring.

## What is committed vs not
- Committed: `tree_hash.py`, `capture_converter.py`, this README, the tests.
- NOT committed (gitignored): `tests/golden/*.json`, any sample data.

## Capture the converter baseline (run once, locally)
1. Make a local copy of valid sample `UserData` and a `config.yaml` whose
   `converter_paths.output_path` points at a scratch folder. Keep it OUTSIDE git.
2. In PowerShell:
   ```powershell
   $env:PIT_ORIG_CONVERTER  = "C:\...\Projects\RICS_BulkImportFiles_Converter"
   $env:PIT_CONVERTER_CONFIG = "C:\scratch\convert\config.yaml"
   python tests/golden_master/capture_converter.py C:\scratch\convert\RICS_Files\20250630
   ```
3. Confirm `tests/golden/converter_manifest.json` was written.

## How Part 2 uses it
After the converter is refactored into `pit.converter`, a test runs the NEW
converter on the SAME sample config, hashes the output tree, and asserts
`diff_manifests(golden, new) == []`. Any difference fails the build.

The importer baseline (Part 3) is captured analogously on the parsed-config +
generated-YAML, with the SG boundary mocked — added when Part 3 is planned.
```

- [ ] **Step 7: Commit**

```bash
git add tests/golden_master/
git commit -m "feat: golden-master capture/compare harness"
```

---

## Self-Review

**Spec coverage (foundation slice of the spec):**
- §4 structure — `pit/`, `pit/shared/` (results, config, logging), `tests/`, `pyproject`, `.gitignore`, `excelTool/` ignore rule: covered by Tasks 1–4. ✓
- §3 tool independence / §7.4 single results contract — Task 2 (`write_results` takes per-tool filename; `summary_file` optional). ✓
- §7.2 schema-validated config with clear errors — Task 3. ✓
- §7.6 centralized logging — Task 4. ✓
- §9 golden-master strategy — Task 5 (capture + compare; importer capture deferred to its own plan). ✓
- §8 "No data committed" — `.gitignore` (Task 1) ignores `tests/fixtures/`, `tests/golden/`, `sample_data/`, `*.xlsm`. ✓

**Out of this plan (later plans):** Converter backend migration (Part 2), Importer backend
(Part 3), unified VBA (Part 4), workbook builder (Part 5), PyInstaller specs (Part 6), docs
(Part 7). Each gets its own plan after this foundation is green and reviewed.

**Placeholder scan:** none — every code step contains complete code.

**Type consistency:** `Result.success/error/to_dict` and `write_results(result, out_dir,
filename)` are used consistently; `hash_tree/write_manifest/diff_manifests` signatures match
between implementation, tests, and `capture_converter.py`.

**Note vs spec:** For end-to-end golden masters this plan captures baselines from local
sample data (gitignored) rather than synthetic `make_fixtures` output, because synthetic
inputs are unlikely to survive the full GCorr pipeline. Principle ("no data committed",
reproducible harness) is preserved; `make_fixtures` remains available for pure-function unit
tests in later plans.
```
