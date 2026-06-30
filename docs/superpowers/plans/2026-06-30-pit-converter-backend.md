# PIT Converter Backend Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the original RICS converter (`RICS_BulkImportFiles_Converter/main.py` + `Userful_Functions/`) into `pit/converter/`, refactored to a testable `pipeline.run(config) -> dict` with a processor registry and a `cli.py` entry point, **proven byte-for-byte identical** to the original via the golden-master harness from Plan 1.

**Architecture:** The heavy processor modules are vendored almost verbatim (behavior frozen by the golden master) with only their intra-package imports rewritten. The orchestration that today lives in `main.py`'s module body + `__main__` block is lifted into `pipeline.run(config)` (no import-time side effects). The `if/elif` data-type dispatch becomes a small registry. A new `cli.py` mirrors the original `excel_wrapper.py` but uses the Plan-1 shared modules (`config`, `logging_setup`, `results`).

**Tech Stack:** Python 3.11+, pandas, numpy, openpyxl, PyYAML, pytest. Windows.

## Global Constraints

- The converted **output tree must be byte-for-byte identical** to the original converter's output for the same inputs. The golden-master equivalence test (Task 6) is the gate.
- Vendored processor modules are **moved, not rewritten**: copy verbatim, change only `import` lines and remove dead imports. Any logic edit is out of scope.
- No import-time side effects anywhere in `pit/converter/` — importing a module must not read files or run conversion.
- `pipeline.run(config)` replicates `main.py` exactly, including `output_dir = config['converter_paths']['output_path']` (NO date subfolder).
- Reference data (`MoodysInternalData`) and all client/sample data are **never committed** — resolved from a path at runtime; `pit/converter/data/` is gitignored.
- Package name `pit`; tool name "Portfolio Import Tool"; converter exe is `Converter.exe`; results filename `rics_converter_results.json`; log filename `rics_converter.log`.
- Source of truth for original behavior: `C:\Users\peic\OneDrive - Moody's\Documents\POCs\Projects\RICS_BulkImportFiles_Converter` (referred to below as `<ORIG>`).

---

### Task 1: Vendor the processor modules

**Files:**
- Create: `pit/converter/__init__.py` (empty)
- Create: `pit/converter/processors/__init__.py` (empty)
- Create (copy from `<ORIG>`): `pit/converter/processors/userdata.py` ← `Userful_Functions/UserData_Processor.py`
- Create (copy): `pit/converter/processors/convert_to_rics.py` ← `Userful_Functions/Convert_to_RICS.py`
- Create (copy): `pit/converter/processors/update_import_files.py` ← `Userful_Functions/Update_RICS_Import_Files.py`
- Create (copy): `pit/converter/processors/granular.py` ← `Userful_Functions/GC_GCCRE_GCRETAIL_processor.py`
- Create (copy): `pit/converter/processors/agency_mbs.py` ← `Userful_Functions/AgencyMBS_processor.py`
- Create (copy): `pit/converter/processors/portfolio.py` ← `Userful_Functions/portfolio_processor.py`
- Test: `tests/converter/__init__.py`, `tests/converter/test_convert_to_rics_pure.py`

**Interfaces:**
- Consumes: nothing from Plan 1.
- Produces (public symbols later tasks rely on, signatures unchanged from original):
  - `userdata.load_user_data(data_types, file_types, user_data_path) -> dict`
  - `userdata.load_mapping_tables(mapping_file, mapping_tables) -> dict`
  - `convert_to_rics.read_rics_import_format(csv_path) -> dict`
  - `convert_to_rics.apply_rics_version_format_filter(rics_import_format, rics_version) -> dict`
  - `convert_to_rics.rics_version_gte(version_str, target) -> bool`
  - `granular.GC_GCCRE_GCRETAIL(type, start_date, data, GCorr_data, parameters_default_values, rics_import_format, output_dir, mapping_data, rics_version="10.6")` with `.run() -> dict`
  - `agency_mbs.AgencyMBS(type, data, rics_import_format, output_path)` with `.run() -> dict`
  - `portfolio.Portfolio(data, rics_import_format, output_path, portfolio_subdir="portfolio")` with `.run() -> dict`

- [ ] **Step 1: Copy the six modules verbatim and add package markers**

Copy each `<ORIG>` file to its new path with identical content, then create the two empty `__init__.py` files and `tests/converter/__init__.py`. Use the file mapping in **Files** above.

- [ ] **Step 2: Rewrite imports in the three modules that referenced the old package**

In `pit/converter/processors/granular.py`:
- DELETE line 1 entirely: `from doctest import REPORT_ONLY_FIRST_FAILURE` (dead import).
- Replace `from Userful_Functions.Convert_to_RICS import *` with `from pit.converter.processors.convert_to_rics import *`
- Replace `from Userful_Functions.Update_RICS_Import_Files import *` with `from pit.converter.processors.update_import_files import *`

In `pit/converter/processors/agency_mbs.py`:
- Replace `from Userful_Functions.Convert_to_RICS import *` with `from pit.converter.processors.convert_to_rics import *`

In `pit/converter/processors/portfolio.py`:
- Replace `from Userful_Functions.Convert_to_RICS import *` with `from pit.converter.processors.convert_to_rics import *`

(`userdata.py`, `convert_to_rics.py`, `update_import_files.py` import only stdlib + pandas/numpy — no changes needed. Verify by reading their import lines.)

- [ ] **Step 3: Write the failing characterization tests for two pure functions**

These prove the move preserved behavior without needing any data files.

```python
# tests/converter/test_convert_to_rics_pure.py
from pit.converter.processors.convert_to_rics import (
    rics_version_gte,
    apply_rics_version_format_filter,
)


def test_rics_version_gte_basic():
    assert rics_version_gte("10.6", "10.6") is True
    assert rics_version_gte("10.7", "10.6") is True
    assert rics_version_gte("11.0", "10.6") is True
    assert rics_version_gte("10.5", "10.6") is False
    assert rics_version_gte("10", "10.6") is False  # minor defaults to 0


def test_rics_version_gte_blank_or_none():
    assert rics_version_gte(None, "10.6") is False
    assert rics_version_gte("", "10.6") is False
    assert rics_version_gte("   ", "10.6") is False


def test_format_filter_drops_rbcfactors_below_106():
    fmt = {
        "ChildBond": ["Name", "RBCFactors", "Coupon"],
        "ChildFRN": ["Name", "RBCFactors"],
        "Other": ["RBCFactors"],  # not a child table -> untouched
    }
    out = apply_rics_version_format_filter(fmt, "10.5")
    assert out["ChildBond"] == ["Name", "Coupon"]
    assert out["ChildFRN"] == ["Name"]
    assert out["Other"] == ["RBCFactors"]


def test_format_filter_keeps_rbcfactors_at_106_and_is_a_copy():
    fmt = {"ChildBond": ["Name", "RBCFactors"]}
    out = apply_rics_version_format_filter(fmt, "10.6")
    assert out["ChildBond"] == ["Name", "RBCFactors"]
    # mutating the output must not change the input (defensive copy)
    out["ChildBond"].append("X")
    assert fmt["ChildBond"] == ["Name", "RBCFactors"]
```

- [ ] **Step 4: Run — expect import failure first, then pass**

Run: `python -m pytest tests/converter/test_convert_to_rics_pure.py -v`
Expected after Steps 1-2: PASS (4 tests). If it fails with `ModuleNotFoundError: No module named 'Userful_Functions'`, an import rewrite in Step 2 was missed — fix it.

- [ ] **Step 5: Verify the whole package imports cleanly (no side effects)**

Run: `python -c "import pit.converter.processors.granular, pit.converter.processors.agency_mbs, pit.converter.processors.portfolio, pit.converter.processors.userdata; print('ok')"`
Expected: prints `ok` with no file access or errors.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q`
Expected: all prior tests + 4 new = green.

```bash
git add pit/converter/ tests/converter/
git commit -m "feat: vendor converter processor modules into pit.converter.processors"
```

---

### Task 2: Summary writer (`pit/converter/summary.py`)

**Files:**
- Create: `pit/converter/summary.py` (move `write_summary_file` + `write_granular_counterparty_summary` from `<ORIG>/main.py` lines 82-213, verbatim)
- Test: `tests/converter/test_summary.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `summary.write_summary_file(output_dir, start_date, summaries) -> str` (returns the summary file path) and `summary.write_granular_counterparty_summary(f, title, summary_data)`.

- [ ] **Step 1: Move the two functions verbatim into `summary.py`**

Copy `write_granular_counterparty_summary` (lines 82-136) and `write_summary_file` (lines 139-213) from `<ORIG>/main.py` into `pit/converter/summary.py` exactly. Add `import os` and `import datetime` at the top (the originals use them). Do not change the body.

- [ ] **Step 2: Write the failing test**

```python
# tests/converter/test_summary.py
import os

from pit.converter.summary import write_summary_file


def test_write_summary_creates_file_with_sections(tmp_path):
    summaries = {
        "gc": {
            "data_type": "GC",
            "num_issuers": 3,
            "num_factors": 2,
            "num_instruments": 5,
            "1_GCP": {"rows": 5, "unique_names": 3},
        },
        "portfolio": {
            "num_portfolios": 1,
            "num_holdings_per_portfolio": {"PortA": 4},
        },
        "agency_mbs": None,
    }
    path = write_summary_file(str(tmp_path), "20250630", summaries)
    assert path == os.path.join(str(tmp_path), "RICS_Format_Converter_Summary.txt")
    text = open(path, encoding="utf-8").read()
    assert "RICS FORMAT CONVERTER - PROCESSING SUMMARY" in text
    assert "Processing Date: 20250630" in text
    assert "GC (CORPORATE) PROCESSING" in text
    assert "PORTFOLIO PROCESSING" in text
    assert "PortA: 4 holdings" in text
    assert "PROCESSING COMPLETED SUCCESSFULLY" in text
```

- [ ] **Step 3: Run to verify it fails, then passes**

Run: `python -m pytest tests/converter/test_summary.py -v`
Expected: FAIL first (`ModuleNotFoundError: pit.converter.summary`); PASS after Step 1 (1 test).

- [ ] **Step 4: Commit**

```bash
git add pit/converter/summary.py tests/converter/test_summary.py
git commit -m "feat: converter summary writer (extracted from main.py)"
```

---

### Task 3: Processor registry (`pit/converter/processors/registry.py`)

**Files:**
- Create: `pit/converter/processors/registry.py`
- Test: `tests/converter/test_registry.py`

**Interfaces:**
- Consumes: `granular.GC_GCCRE_GCRETAIL`, `agency_mbs.AgencyMBS`.
- Produces:
  - `@dataclass HandlerContext` with fields: `start_date: str`, `rics_version: str`, `gcorr_data: dict`, `params: dict`, `rics_format: dict`, `mapping_data: dict`, `output_dir_granular: str`.
  - `get_handler(data_type_upper: str) -> Optional[Callable]` returning a handler for `"GC"`, `"GCCRE"`, `"GCRETAIL"`, `"AGENCYMBS"`, else `None`.
  - Each handler has signature `handler(data_type_upper: str, data: dict, ctx: HandlerContext) -> tuple[str, dict, list]` returning `(summary_key, summary, matured_or_removed_instruments)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/converter/test_registry.py
from pit.converter.processors.registry import HandlerContext, get_handler


def test_known_types_have_handlers():
    for dt in ("GC", "GCCRE", "GCRETAIL", "AGENCYMBS"):
        assert get_handler(dt) is not None


def test_unknown_type_returns_none():
    assert get_handler("FOO") is None
    assert get_handler("gc") is None  # registry keys are upper-case


def test_handler_context_fields():
    ctx = HandlerContext(
        start_date="20250630", rics_version="10.6", gcorr_data={},
        params={}, rics_format={}, mapping_data={}, output_dir_granular="C:/out",
    )
    assert ctx.start_date == "20250630"
    assert ctx.output_dir_granular == "C:/out"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/converter/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: pit.converter.processors.registry`

- [ ] **Step 3: Implement the registry**

```python
# pit/converter/processors/registry.py
"""Data-type -> processor dispatch for the converter.

Replaces the original main.py if/elif chain. A new granular type is added by
registering a handler — pipeline.run does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from pit.converter.processors.granular import GC_GCCRE_GCRETAIL
from pit.converter.processors.agency_mbs import AgencyMBS


@dataclass
class HandlerContext:
    start_date: str
    rics_version: str
    gcorr_data: dict
    params: dict
    rics_format: dict
    mapping_data: dict
    output_dir_granular: str


_REGISTRY: dict = {}


def _register(*data_types):
    def deco(fn):
        for dt in data_types:
            _REGISTRY[dt] = fn
        return fn
    return deco


def get_handler(data_type_upper: str) -> Optional[Callable]:
    return _REGISTRY.get(data_type_upper)


@_register("GC", "GCCRE", "GCRETAIL")
def _handle_granular(data_type_upper: str, data: dict, ctx: HandlerContext):
    proc = GC_GCCRE_GCRETAIL(
        data_type_upper, ctx.start_date, data, ctx.gcorr_data, ctx.params,
        ctx.rics_format, ctx.output_dir_granular, ctx.mapping_data, ctx.rics_version,
    )
    summary = proc.run()
    matured = summary.get("matured_instruments", []) if summary else []
    return data_type_upper.lower(), summary, matured


@_register("AGENCYMBS")
def _handle_agency_mbs(data_type_upper: str, data: dict, ctx: HandlerContext):
    proc = AgencyMBS("AgencyMBS", data, ctx.rics_format, ctx.output_dir_granular)
    summary = proc.run()
    removed = summary.get("removed_instruments", []) if summary else []
    return "agency_mbs", summary, removed
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/converter/test_registry.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pit/converter/processors/registry.py tests/converter/test_registry.py
git commit -m "feat: converter processor registry (replaces if/elif dispatch)"
```

---

### Task 4: Pipeline orchestration (`pit/converter/pipeline.py`)

**Files:**
- Create: `pit/converter/pipeline.py`
- Test: `tests/converter/test_pipeline.py`

**Interfaces:**
- Consumes: `pit.shared.config.require`, `userdata`, `convert_to_rics`, `registry`, `summary`.
- Produces: `pipeline.run(config: dict) -> dict` (returns the `summaries` dict). Raises `pit.shared.config.ConfigError` if required keys are missing.

**Behavioral fidelity:** this is `<ORIG>/main.py`'s module body + `__main__` block, restructured into a function. Keep identical: `output_dir = output_path` (no date join); granular skip-warnings; matured-instrument collection and portfolio filtering; GCorr loading branch by version.

- [ ] **Step 1: Write the failing tests (no data needed)**

```python
# tests/converter/test_pipeline.py
import pytest

from pit.converter import pipeline
from pit.shared.config import ConfigError


def test_import_has_no_side_effects():
    # Importing pipeline must not read files or run anything.
    import importlib
    importlib.reload(pipeline)  # should not raise


def test_run_raises_configerror_on_missing_keys():
    with pytest.raises(ConfigError) as exc:
        pipeline.run({})
    msg = str(exc.value)
    assert "start_date" in msg
    assert "converter_paths.output_path" in msg
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/converter/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: pit.converter.pipeline`

- [ ] **Step 3: Implement `pipeline.py`**

```python
# pit/converter/pipeline.py
"""Converter orchestration. Refactored from the original main.py into a pure
run(config) -> summaries function with no import-time side effects.
"""
from __future__ import annotations

import os

import pandas as pd

from pit.shared.config import require
from pit.converter.processors.userdata import load_user_data, load_mapping_tables
from pit.converter.processors.convert_to_rics import (
    read_rics_import_format,
    apply_rics_version_format_filter,
)
from pit.converter.processors.registry import HandlerContext, get_handler
from pit.converter.processors.portfolio import Portfolio
from pit.converter.summary import write_summary_file

REQUIRED_KEYS = [
    "start_date",
    "GCorr_Corporate_version",
    "converter_paths.output_path",
    "moodys_internal_data",
]


def _load_gcorr_data(gcorr_info: dict, version: str) -> dict:
    data = {}
    if version == "2019":
        data["factors"] = pd.read_excel(gcorr_info["file_name"], sheet_name=gcorr_info["tabs"]["factors"])
        data["rsqs"] = pd.read_excel(gcorr_info["file_name"], sheet_name=gcorr_info["tabs"]["rsqs"])
    else:
        tmp = pd.read_csv(gcorr_info["file_name"]).rename(columns={"GCorrRsq": "RSQ"})
        data["factors"] = tmp.copy()
        data["rsqs"] = tmp[["pid", "RSQ"]].copy()
    return data


def _build_gcorr_info(config: dict, gcorr_corp_path: str, version: str) -> dict:
    base_filename = config["GCorr_files"]["file_name"].format(version=version)
    info: dict = {}
    if version == "2019":
        info["file_name"] = os.path.join(gcorr_corp_path, f"{base_filename}.xlsx")
        info["tabs"] = {
            "factors": config["GCorr_files"]["factors"].format(version=version),
            "rsqs": config["GCorr_files"]["rsqs"].format(version=version),
        }
    else:
        info["file_name"] = os.path.join(gcorr_corp_path, f"{base_filename}.csv")
        info["tabs"] = {}
    return info


def _process_portfolio(portfolio_data, all_matured, rics_import_format, output_dir):
    if not portfolio_data:
        print(f"Warning: Portfolio folder not found. Skipping portfolio processing.")
        return None
    key = "PORTFOLIO" if "PORTFOLIO" in portfolio_data else "portfolio"
    if key not in portfolio_data:
        print("Warning: Portfolio data not found (check configuration). Skipping.")
        return None
    files = portfolio_data[key]
    if not files or all(v is None for v in files.values()):
        print("Warning: No valid portfolio files found. Skipping.")
        return None

    if all_matured:
        print(f"\nFiltering {len(all_matured)} matured/removed instruments from holdings...")
        holdings_df = portfolio_data[key].get("Holdings")
        if holdings_df is not None and not holdings_df.empty:
            original_count = len(holdings_df)
            holdings_df["InstrumentID"] = (
                holdings_df["counterpartyName"].astype(str) + "."
                + holdings_df["instrumentName"].astype(str)
            )
            portfolio_data[key]["Holdings"] = (
                holdings_df[~holdings_df["InstrumentID"].isin(all_matured)]
                .drop(columns=["InstrumentID"]).reset_index(drop=True)
            )
            removed = original_count - len(portfolio_data[key]["Holdings"])
            print(f"  Removed {removed} matured/removed instrument holdings.")

    return Portfolio(portfolio_data[key], rics_import_format, output_dir).run()


def run(config: dict) -> dict:
    require(config, REQUIRED_KEYS)

    start_date = config["start_date"]
    gcorr_version = config["GCorr_Corporate_version"]
    rics_version = config.get("RICS_version", "10.6")

    data_path = config["converter_paths"].get("data_path", "")
    granular_path = os.path.join(data_path, "granularCounterparty")
    portfolio_path = os.path.join(data_path, "portfolio")
    output_dir = config["converter_paths"]["output_path"]

    granular_types = config["converter_data_types"]["granular"]
    portfolio_types = config["converter_data_types"]["portfolio"]
    granular_file_types = config["file_types"]["granular"]
    portfolio_file_types = config["file_types"]["portfolio"]

    moodys_data_path = config["moodys_internal_data"]
    gcorr_corp_path = os.path.join(
        moodys_data_path, config["GCorr_Corporate"].format(version=gcorr_version)
    )
    rics_format_file = os.path.join(moodys_data_path, "RICS_BulkImportFiles_Formats.csv")
    gcorr_info = _build_gcorr_info(config, gcorr_corp_path, gcorr_version)

    params = config["parameters_default_values"]
    mapping_file = config["Mapping_File"]
    mapping_tables = config["Mapping_Tables"]

    os.makedirs(output_dir, exist_ok=True)

    rics_import_format = read_rics_import_format(rics_format_file)
    rics_import_format = apply_rics_version_format_filter(rics_import_format, rics_version)
    mapping_data = load_mapping_tables(os.path.join(moodys_data_path, mapping_file), mapping_tables)
    gcorr_data = _load_gcorr_data(gcorr_info, gcorr_version)

    summaries: dict = {}
    all_matured: list = []

    data = load_user_data(granular_types, granular_file_types, granular_path)
    if granular_types:
        output_dir_granular = os.path.join(output_dir, "granularCounterparty")
        os.makedirs(output_dir_granular, exist_ok=True)
        ctx = HandlerContext(
            start_date=start_date, rics_version=rics_version, gcorr_data=gcorr_data,
            params=params, rics_format=rics_import_format, mapping_data=mapping_data,
            output_dir_granular=output_dir_granular,
        )
        for data_type in granular_types:
            dt = data_type.upper()
            if dt not in data:
                print(f"Warning: No data found for {data_type}. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            files = data[dt]
            if not files or all(v is None for v in files.values()):
                print(f"Warning: No valid files found for {data_type}. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            handler = get_handler(dt)
            if handler is None:
                print(f"Warning: Unknown data type '{data_type}'. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            summary_key, summary, matured = handler(dt, data[dt], ctx)
            summaries[summary_key] = summary
            all_matured.extend(matured)

    portfolio_data = load_user_data(portfolio_types, portfolio_file_types, portfolio_path)
    summaries["portfolio"] = _process_portfolio(
        portfolio_data, all_matured, rics_import_format, output_dir
    )

    write_summary_file(output_dir, start_date, summaries)
    print("RICS bulk import files generated successfully for date:", start_date)
    return summaries
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/converter/test_pipeline.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pit/converter/pipeline.py tests/converter/test_pipeline.py
git commit -m "feat: converter pipeline.run (refactored from main.py, registry-driven)"
```

---

### Task 5: CLI entry point (`pit/converter/cli.py`)

**Files:**
- Create: `pit/converter/cli.py`
- Test: `tests/converter/test_cli.py`

**Interfaces:**
- Consumes: `pit.version.__version__`, `pit.shared.config.load_config/ConfigError`, `pit.shared.logging_setup.setup_logging`, `pit.shared.results.Result/write_results`, `pit.converter.pipeline.run`.
- Produces:
  - `cli.convert_excel_config_to_internal(excel_config: dict) -> dict` (mirrors original wrapper).
  - `cli.resolve_moodys_data(config: dict) -> str` (multi-location search; raises `FileNotFoundError` if not found).
  - `cli.run_converter_with_config(config: dict) -> int` (sets up logging next to the exe/script, resolves Moody's data, calls `pipeline.run`, writes results JSON, returns 0/1).
  - `cli.main(argv: list | None = None) -> int` (handles `--help`/`--version`/`--json`/config-path/default).

- [ ] **Step 1: Write the failing tests**

```python
# tests/converter/test_cli.py
import json
import os

import pytest

from pit.converter import cli


def test_version_returns_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "Portfolio Import Tool Converter" in capsys.readouterr().out


def test_help_returns_zero():
    assert cli.main(["--help"]) == 0


def test_missing_config_file_returns_one(capsys):
    assert cli.main(["Z:/no/such/config.yaml"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_excel_config_mapping_has_expected_shape():
    internal = cli.convert_excel_config_to_internal({
        "start_date": "20250630",
        "data_path": "C:/d", "output_path": "C:/o",
    })
    assert internal["start_date"] == "20250630"
    assert internal["converter_paths"]["data_path"] == "C:/d"
    assert internal["converter_paths"]["output_path"] == "C:/o"
    assert "file_types" in internal
    assert "GCorr_files" in internal


def test_resolve_moodys_data_finds_dir(tmp_path):
    d = tmp_path / "MoodysInternalData"
    d.mkdir()
    (d / "RICS_BulkImportFiles_Formats.csv").write_text("x\n", encoding="utf-8")
    config = {"moodys_internal_data": str(d)}
    assert os.path.normpath(cli.resolve_moodys_data(config)) == os.path.normpath(str(d))


def test_resolve_moodys_data_raises_when_absent(tmp_path):
    config = {"moodys_internal_data": str(tmp_path / "nope")}
    with pytest.raises(FileNotFoundError):
        cli.resolve_moodys_data(config)


def test_run_with_config_writes_results_and_returns_zero(tmp_path, monkeypatch):
    # Moody's data dir with the sentinel file so resolution passes.
    md = tmp_path / "MoodysInternalData"
    md.mkdir()
    (md / "RICS_BulkImportFiles_Formats.csv").write_text("x\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    config = {
        "moodys_internal_data": str(md),
        "converter_paths": {"output_path": str(out)},
    }
    # Stub the heavy pipeline; we are testing CLI wiring, not conversion.
    monkeypatch.setattr(cli.pipeline, "run", lambda cfg: {"ok": True})
    # Write results next to the cli module's dir — redirect to tmp by stubbing _script_dir.
    monkeypatch.setattr(cli, "_script_dir", lambda: str(out))
    rc = cli.run_converter_with_config(config)
    assert rc == 0
    results = json.load(open(os.path.join(str(out), "rics_converter_results.json")))
    assert results["status"] == "success"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/converter/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: pit.converter.cli`

- [ ] **Step 3: Implement `cli.py`**

```python
# pit/converter/cli.py
"""Converter CLI — the entry point compiled into Converter.exe.

Mirrors the original excel_wrapper.py contract (config file, or --json from
Excel) but uses the shared config/logging/results modules.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Optional

from pit.version import __version__
from pit.shared.config import load_config, ConfigError
from pit.shared.logging_setup import setup_logging
from pit.shared.results import Result, write_results
from pit.converter import pipeline

RESULTS_FILENAME = "rics_converter_results.json"
LOG_FILENAME = "rics_converter.log"
SUMMARY_FILENAME = "RICS_Format_Converter_Summary.txt"


def _script_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def convert_excel_config_to_internal(excel_config: dict) -> dict:
    return {
        "start_date": excel_config.get("start_date", "20250630"),
        "GCorr_Corporate_version": excel_config.get("GCorr_Corporate_version", "2019"),
        "RICS_version": excel_config.get("RICS_version", "10.6"),
        "converter_paths": {
            "data_path": excel_config.get("data_path", "./UserData"),
            "output_path": excel_config.get("output_path", "./RICS_Files"),
        },
        "converter_data_types": excel_config.get("converter_data_types", {
            "granular": ["GC", "GCCRE", "AgencyMBS"],
            "portfolio": ["portfolio"],
        }),
        "parameters_default_values": excel_config.get("parameters_default_values", {
            "ImpliedCreditClass_default_value": True,
            "CreditClass_default_value": "CS15",
            "interpolate_lgd_lgdk_for_amortising": False,
            "Using_GCorr_Corp_RSQ": False,
            "Using_GCorr_Corp_country": True,
            "Using_GCorr_Corp_industry": False,
            "corp_rsq_fill_default_value": True,
            "corp_rsq_default_value": 0.159719318,
            "corp_factors_fill_value_groupby": True,
            "corp_private_groupby_columnName": "securityType",
        }),
        "file_types": {
            "granular": ["issuers", "factors", "pds", "instruments", "lgd",
                         "cashflows", "couponPayments", "laggard"],
            "portfolio": ["Portfolios", "Holdings"],
        },
        "moodys_internal_data": excel_config.get("moodys_internal_data", "./MoodysInternalData/"),
        "GCorr_Corporate": "GCorr{version}",
        "GCorr_files": {
            "file_name": "GCorr {version} Corp R-Squared Factors",
            "factors": "GCorrCorpFactors{version}",
            "rsqs": "RatingRSQGCorr{version}",
        },
        "Mapping_File": "GCorr_MappingTables.xlsx",
        "Mapping_Tables": {
            "country": "CountryNameMapping",
            "countryRegion": "GCorrFactosMappping",
        },
        "model_assumptions": {"RSQ": {"GC": 0.159719318, "GCCRE": 0.2077}},
        "floating_reference_yield_curves": {"USD 0-EDF SPOT": "NominalYieldCurve"},
    }


def resolve_moodys_data(config: dict) -> str:
    relative = config.get("moodys_internal_data", "./MoodysInternalData/")
    script_dir = _script_dir()
    candidates = []
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", script_dir)
        candidates.append(os.path.join(bundle, "MoodysInternalData"))
    candidates += [
        relative,
        os.path.join(script_dir, "MoodysInternalData"),
        os.path.join(os.path.dirname(script_dir), "MoodysInternalData"),
        os.path.abspath("MoodysInternalData"),
    ]
    if not os.path.isabs(relative):
        candidates.append(os.path.abspath(os.path.join(script_dir, relative)))
        candidates.append(os.path.abspath(relative))
    for loc in candidates:
        loc = os.path.normpath(loc)
        if os.path.isdir(loc) and os.path.exists(os.path.join(loc, "RICS_BulkImportFiles_Formats.csv")):
            return os.path.abspath(loc)
    raise FileNotFoundError(
        "MoodysInternalData folder with RICS_BulkImportFiles_Formats.csv not found. Searched:\n"
        + "\n".join(f"  - {os.path.normpath(c)}" for c in candidates)
    )


def run_converter_with_config(config: dict) -> int:
    out_dir = _script_dir()
    log_path = setup_logging(os.path.join(out_dir, LOG_FILENAME))
    logger = logging.getLogger(__name__)
    try:
        config["moodys_internal_data"] = resolve_moodys_data(config)
        pipeline.run(config)
        output_path = config["converter_paths"]["output_path"]
        summary_file = os.path.join(output_path, SUMMARY_FILENAME)
        result = Result.success(
            "Conversion completed successfully",
            output_path=output_path,
            summary_file=summary_file if os.path.exists(summary_file) else None,
            log_file=log_path,
        )
        write_results(result, out_dir, RESULTS_FILENAME)
        return 0
    except Exception as exc:
        logger.error("CONVERSION FAILED: %s\n%s", exc, traceback.format_exc())
        write_results(Result.error(str(exc), log_file=log_path), out_dir, RESULTS_FILENAME)
        return 1


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        arg = argv[0]
        if arg in ("--help", "-h"):
            print("Portfolio Import Tool - Converter\n\n"
                  "Usage:\n"
                  "  Converter.exe [config.yaml]   Use a YAML config file\n"
                  "  Converter.exe --json <json>   Use a JSON config (from Excel)\n"
                  "  Converter.exe --version       Show version")
            return 0
        if arg in ("--version", "-v"):
            print(f"Portfolio Import Tool Converter {__version__}")
            return 0
        if arg == "--json":
            if len(argv) < 2:
                print("Error: --json requires a JSON string argument", file=sys.stderr)
                return 1
            config = convert_excel_config_to_internal(json.loads(argv[1]))
            return run_converter_with_config(config)
        config_path = arg
        if not os.path.exists(config_path):
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            return 1
        try:
            config = load_config(config_path)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return run_converter_with_config(config)

    if not os.path.exists("config.yaml"):
        print("Error: no config provided and config.yaml not found", file=sys.stderr)
        return 1
    return run_converter_with_config(load_config("config.yaml"))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/converter/test_cli.py -v`
Expected: 7 passed.

- [ ] **Step 5: Run full suite and commit**

Run: `python -m pytest -q`
Expected: green.

```bash
git add pit/converter/cli.py tests/converter/test_cli.py
git commit -m "feat: converter CLI entry point (Converter.exe)"
```

---

### Task 6: Golden-master equivalence test + example config

**Files:**
- Create: `configs/convert.example.yaml`
- Create: `tests/converter/test_golden_equivalence.py`
- Modify: `tests/golden_master/README.md` (add the "verify the refactor" section)

**Interfaces:**
- Consumes: `pit.converter.pipeline.run`, `tests.golden_master.tree_hash.hash_tree/diff_manifests`.
- Produces: an opt-in pytest that re-runs the NEW pipeline on the same sample config and asserts its output tree hashes identically to the Plan-1 baseline.

**How it stays green without data:** the test SKIPS unless `PIT_GOLDEN=1` is set AND both the baseline manifest and the sample config exist. So normal `pytest` runs (CI, other machines) pass; the equivalence check runs only where the local baseline was captured.

- [ ] **Step 1: Create the example config**

```yaml
# configs/convert.example.yaml
# Example Converter config. Copy, edit paths, and pass to Converter.exe:
#   Converter.exe convert.example.yaml
start_date: "20250630"
RICS_version: "10.6"
GCorr_Corporate_version: "2019"

converter_paths:
  data_path: "./UserData"
  output_path: "./RICS_Files"

converter_data_types:
  granular: ["GC", "GCCRE", "AgencyMBS"]
  portfolio: ["portfolio"]

parameters_default_values:
  ImpliedCreditClass_default_value: true
  CreditClass_default_value: "CS15"
  interpolate_lgd_lgdk_for_amortising: false
  Using_GCorr_Corp_RSQ: false
  Using_GCorr_Corp_country: true
  Using_GCorr_Corp_industry: false
  corp_rsq_fill_default_value: true
  corp_rsq_default_value: 0.159719318
  corp_factors_fill_value_groupby: true
  corp_private_groupby_columnName: "securityType"

file_types:
  granular: ["issuers", "factors", "pds", "instruments", "lgd", "cashflows", "couponPayments", "laggard"]
  portfolio: ["Portfolios", "Holdings"]

moodys_internal_data: "./MoodysInternalData/"
GCorr_Corporate: "GCorr{version}"
GCorr_files:
  file_name: "GCorr {version} Corp R-Squared Factors"
  factors: "GCorrCorpFactors{version}"
  rsqs: "RatingRSQGCorr{version}"
Mapping_File: "GCorr_MappingTables.xlsx"
Mapping_Tables:
  country: "CountryNameMapping"
  countryRegion: "GCorrFactosMappping"
model_assumptions:
  RSQ:
    GC: 0.159719318
    GCCRE: 0.2077
floating_reference_yield_curves:
  "USD 0-EDF SPOT": "NominalYieldCurve"
```

- [ ] **Step 2: Write the opt-in equivalence test**

```python
# tests/converter/test_golden_equivalence.py
"""Proves the refactored converter produces output identical to the original.

Opt-in: runs only when PIT_GOLDEN=1 and the local baseline + sample config exist
(neither is committed). Otherwise it skips so normal test runs stay green.

Setup (run once, locally, after capturing the Plan-1 baseline):
    $env:PIT_GOLDEN = "1"
    $env:PIT_CONVERT_SAMPLE_CONFIG = "C:\\scratch\\convert\\config.yaml"  # output_path -> a scratch dir
    python -m pytest tests/converter/test_golden_equivalence.py -v
"""
import json
import os

import pytest

from pit.shared.config import load_config
from pit.converter import pipeline
from tests.golden_master.tree_hash import hash_tree, diff_manifests

GOLDEN_MANIFEST = os.path.join("tests", "golden", "converter_manifest.json")


def _should_run():
    return (
        os.environ.get("PIT_GOLDEN") == "1"
        and os.path.exists(GOLDEN_MANIFEST)
        and os.environ.get("PIT_CONVERT_SAMPLE_CONFIG")
        and os.path.exists(os.environ.get("PIT_CONVERT_SAMPLE_CONFIG", ""))
    )


@pytest.mark.skipif(not _should_run(), reason="golden baseline / sample config not configured")
def test_refactored_output_matches_golden():
    config = load_config(os.environ["PIT_CONVERT_SAMPLE_CONFIG"])
    # The sample config's moodys_internal_data must be a real local path.
    summaries = pipeline.run(config)
    assert summaries is not None

    output_tree = config["converter_paths"]["output_path"]
    new_manifest = hash_tree(output_tree)
    golden = json.load(open(GOLDEN_MANIFEST, encoding="utf-8"))

    diffs = diff_manifests(golden, new_manifest)
    assert diffs == [], "Refactored converter output differs from golden master:\n" + "\n".join(diffs)
```

- [ ] **Step 3: Verify it SKIPS cleanly in the default environment**

Run: `python -m pytest tests/converter/test_golden_equivalence.py -v`
Expected: 1 skipped (reason: golden baseline / sample config not configured). The full suite stays green.

- [ ] **Step 4: Append the verify section to the harness README**

Add to `tests/golden_master/README.md`:

```markdown
## Verify the refactor (Plan 2)
After the converter is migrated, prove output equivalence locally:
1. Capture the baseline (see above) so `tests/golden/converter_manifest.json` exists.
2. Point a sample config's `output_path` at a fresh scratch dir and its
   `moodys_internal_data` at the real local reference folder.
3. Run:
   ```powershell
   $env:PIT_GOLDEN = "1"
   $env:PIT_CONVERT_SAMPLE_CONFIG = "C:\scratch\convert\config.yaml"
   python -m pytest tests/converter/test_golden_equivalence.py -v
   ```
4. PASS = the refactored converter is byte-for-byte identical to the original.
```

- [ ] **Step 5: Commit**

```bash
git add configs/convert.example.yaml tests/converter/test_golden_equivalence.py tests/golden_master/README.md
git commit -m "test: golden-master equivalence check + example converter config"
```

---

## Self-Review

**Spec coverage (Converter slice, spec §4/§7/§8 Part 2):**
- `pit/converter/processors/` (userdata, granular, agency_mbs, portfolio, convert_to_rics, update_import_files) — Task 1. ✓
- `pit/converter/processors/registry.py` replacing if/elif — Task 3. ✓
- `pit/converter/pipeline.py` = `run(config)` refactor of main.py, no import-time side effects — Task 4. ✓
- `pit/converter/summary.py` extracted — Task 2. ✓
- `pit/converter/cli.py` entry point (Converter.exe) using shared modules — Task 5. ✓
- Golden-master equivalence (byte-for-byte) — Task 6. ✓
- "No data committed" — example config only; baseline/fixtures stay gitignored (Plan-1 `.gitignore`). ✓

**Placeholder scan:** none — every code step has complete code or exact import-edit instructions for a verbatim file move.

**Type consistency:** `get_handler` returns handlers with signature `(dt, data, ctx) -> (summary_key, summary, matured)`, consumed exactly that way in `pipeline.run`. `HandlerContext` fields constructed in `pipeline.run` match the dataclass. `run_converter_with_config` uses `pipeline.run`, `Result.success/error`, `write_results(result, out_dir, filename)` — all matching Plan-1 signatures. `_script_dir` is monkeypatched in the CLI test exactly as defined.

**Known original quirks preserved (flagged):**
- `main.py` writes output to `output_path` directly (no `start_date` subfolder); the original `excel_wrapper` reported the summary at `output_path/start_date`. `cli.run_converter_with_config` reports the summary at `output_path/RICS_Format_Converter_Summary.txt` — i.e. where `pipeline.run` actually writes it. This corrects a latent path mismatch in the original's *reporting only*; the converted data tree is unchanged and is what the golden master verifies.
- `convert_excel_config_to_internal` is copied faithfully from the original wrapper; the Excel always passes `parameters_default_values` explicitly, so the default branch is never exercised in practice.

**Dependency on Plan 1:** uses `pit.shared.config.require/load_config/ConfigError`, `pit.shared.logging_setup.setup_logging`, `pit.shared.results.Result/write_results`, and `tests.golden_master.tree_hash` — all delivered and green.
