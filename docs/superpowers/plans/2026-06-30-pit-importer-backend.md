# PIT Importer Backend Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the RICS API Bulk Import tool (`RICS_API_BulkImport/RICS_BulkImport_Tool.py` + `Useful_functions/`) into `pit/importer/`, refactored to a testable `pipeline.run(config)` with the Moody's SG/.NET boundary isolated behind a single mockable `sg_api` seam, plus a `cli.py` entry point — fully unit-testable **without** a Moody's SG installation.

**Architecture:** The pure modules (`BHOFileGenerator`, `Read_RICSImportFiles`) are vendored verbatim. The 1,592-line `RICS_BulkImport_Tool.py` is moved to `pipeline.py` with two surgical changes: (1) the import-time CLR/Simulation initialization is removed and relocated into `sg_api.init_sg()`; (2) the module body + `__main__` become `run(config)`. All SG/.NET access flows through a small set of module-level handles (`sim`, `BulkImporter`, `ParameterSetImporter`, `DuplicateImportAction`, `String`, `File`) that `run()` binds from the `sg_api` context — so a `FakeSG` test double can be bound instead, exercising the whole import flow with zero .NET.

**Tech Stack:** Python 3.11+, pandas (pinned `>=2.2,<3`), pythonnet (runtime-only, never imported in tests), PyYAML, pytest. Windows.

## Global Constraints

- **No live SG in tests.** Every test runs with the SG boundary mocked (a `FakeSG`). Importing any `pit.importer` module must NOT load the CLR, import `clr`/`MoodysAnalytics.*`, or construct a `Simulation`. pythonnet/CLR is touched ONLY inside `sg_api.init_sg()` (called at runtime, never at import).
- **Faithful move.** `bho.py` and `read_rics_files.py` are verbatim copies (only import lines may change). The pipeline logic is moved verbatim except the two surgical changes above; do not alter import/SG-call logic.
- `pipeline.run(config)` replicates the original `RICS_BulkImport_Tool.py` `main()` flow exactly (load-or-create sim, import GCs, merge+import portfolios, import economies/transition-matrices/MPR/zscore per flags, generate+import BHO output files, save `.bhs`).
- The two tools stay decoupled: importer uses its OWN results filename `rics_import_results.json` and log `rics_import.log`; it reuses `pit.shared` (config/logging/results) exactly as the converter does. No shared runtime state with the converter.
- Tool name "Portfolio Import Tool"; importer exe is `Importer.exe`.
- Source of truth for original behavior: `C:\Users\peic\OneDrive - Moody's\Documents\POCs\Projects\RICS_API_BulkImport` (referred to below as `<ORIG>`). Architecture reference: the importer maps in this repo's session notes (module-level side effects at `<ORIG>/RICS_BulkImport_Tool.py` lines 29–123; SG boundary = global `sim` + classes `BulkImporter`, `ParameterSetImporter`, `DuplicateImportAction`, `String`, `File`).

---

### Task 1: Vendor the pure modules (BHO + file reader)

**Files:**
- Create: `pit/importer/__init__.py` (empty)
- Create (copy verbatim): `pit/importer/bho.py` ← `<ORIG>/Useful_functions/BHOFileGenerator.py`
- Create (copy verbatim): `pit/importer/read_rics_files.py` ← `<ORIG>/Useful_functions/Read_RICSImportFiles.py`
- Test: `tests/importer/__init__.py`, `tests/importer/test_pure_modules.py`

**Interfaces:**
- Consumes: nothing.
- Produces (signatures unchanged from original):
  - `bho.BHOFileGenerator(output_type, bond_ids, ...)` with `.generate_string() -> str` and `.generate()`.
  - `read_rics_files.merge_folders_to_base(base_dir, base_folder_name, folders_to_merge) -> str`
  - `read_rics_files.read_rics_files(base_dir) -> tuple[dict, dict, list]`
  - `read_rics_files.read_portfolio_files(base_dir)`, `generate_output_bho_files(model_lists, Selection, Outputs, bho_output_path)`

- [ ] **Step 1: Copy both files verbatim**

Use shell `cp` (do not retype). `BHOFileGenerator.py` → `bho.py`; `Read_RICSImportFiles.py` → `read_rics_files.py`. Create the empty `__init__.py` files.

- [ ] **Step 2: Fix the BHOFileGenerator import in read_rics_files.py**

`read_rics_files.py` imports `BHOFileGenerator` (originally `from BHOFileGenerator import ...` or `from Useful_functions.BHOFileGenerator import ...`). Find that import line and change it to:
```python
from pit.importer.bho import BHOFileGenerator
```
(Read the original import line first and match its imported names exactly — e.g. if it imports the class only, import the class only.) Make NO other edits.

- [ ] **Step 3: Write the failing pure-module tests**

```python
# tests/importer/test_pure_modules.py
import os

from pit.importer.bho import BHOFileGenerator
from pit.importer.read_rics_files import merge_folders_to_base, read_rics_files


def test_bho_generate_string_is_valid_xml():
    gen = BHOFileGenerator("TotalReturn", ["IssuerA.Bond1", "IssuerB.Bond2"])
    xml = gen.generate_string()
    assert xml.strip().startswith("<")
    assert "Bond1" in xml or "IssuerA" in xml  # bond ids embedded


def test_merge_folders_to_base_combines_and_returns_path(tmp_path):
    base = tmp_path / "granularCounterparty"
    (base / "GC").mkdir(parents=True)
    (base / "GCP_CLO").mkdir(parents=True)
    (base / "GC" / "1_GCP.csv").write_text("Name,X\na,1\n", encoding="utf-8")
    (base / "GCP_CLO" / "1_GCP.csv").write_text("Name,X\nb,2\n", encoding="utf-8")
    merged = merge_folders_to_base(str(base), "GC", ["GCP_CLO"])
    assert os.path.isdir(merged)


def test_read_rics_files_classifies_subfolders(tmp_path):
    base = tmp_path / "granularCounterparty"
    (base / "GC").mkdir(parents=True)
    (base / "GC" / "1_GCP.csv").write_text("Name\na\n", encoding="utf-8")
    rics_data, rics_info, csv_portfolio_files = read_rics_files(str(base))
    assert "GC" in rics_data
```

> NOTE: the exact assertions for `BHOFileGenerator.generate_string()` output and `read_rics_files` return shape must be confirmed against the real code while implementing — read `bho.py` and `read_rics_files.py` and adjust the asserts to match actual output (e.g. root tag name, dict keys). Keep them behavior-real (assert structure, not trivial truthiness).

- [ ] **Step 4: Run, verify fail→pass**

Run: `python -m pytest tests/importer/test_pure_modules.py -v`
Expected: fails on missing module first; passes after Steps 1-2 (adjust asserts in Step 3 to the real output if needed).

- [ ] **Step 5: Verify clean import (no CLR/SG)**

Run: `python -c "import pit.importer.bho, pit.importer.read_rics_files; print('ok')"`
Expected: `ok` — no pythonnet/clr import, no errors.

- [ ] **Step 6: Commit**

```bash
git add pit/importer/ tests/importer/
git commit -m "feat: vendor importer pure modules (BHO generator, RICS file reader)"
```

---

### Task 2: SG boundary seam (`pit/importer/sg_api.py`) + FakeSG test double

**Files:**
- Create: `pit/importer/sg_api.py`
- Create: `tests/importer/fakes.py`
- Test: `tests/importer/test_sg_api.py`

**Interfaces:**
- Consumes: nothing at import (pythonnet imported lazily inside `init_sg`).
- Produces:
  - `@dataclass SG` with fields `sim`, `BulkImporter`, `ParameterSetImporter`, `DuplicateImportAction`, `String`, `File`.
  - `sg_api.init_sg(runtime_config: str, assembly_path: str, model_path: str, data_path: str, licence_path: str) -> SG` — loads coreclr, adds the SG assembly reference, imports the .NET types, constructs+licences a `Simulation`, returns an `SG`. This is the ONLY function that imports `clr`/`pythonnet`/`MoodysAnalytics.*`.
  - `tests/importer/fakes.py`: `FakeSG()` exposing `.sim`, `.BulkImporter`, `.ParameterSetImporter`, `.DuplicateImportAction`, `.String`, `.File` whose methods record calls into `FakeSG.calls` (a list of `(name, args)`), satisfying the mock interface the pipeline uses (see below).

- [ ] **Step 1: Write the failing tests**

```python
# tests/importer/test_sg_api.py
import importlib

import pit.importer.sg_api as sg_api
from tests.importer.fakes import FakeSG


def test_importing_sg_api_does_not_load_clr():
    # Reimport must not raise / must not require pythonnet at import time.
    importlib.reload(sg_api)
    assert hasattr(sg_api, "init_sg")
    assert hasattr(sg_api, "SG")


def test_fake_sg_records_calls():
    sg = FakeSG()
    model = sg.sim.Create("RICS")
    sg.sim.Save("out.bhs")
    names = [c[0] for c in sg.calls]
    assert "sim.Create" in names
    assert "sim.Save" in names
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/importer/test_sg_api.py -v`
Expected: FAIL — module/fakes missing.

- [ ] **Step 3: Implement `sg_api.py`**

```python
# pit/importer/sg_api.py
"""The ONLY Moody's SG / .NET boundary.

pythonnet/CLR is imported lazily inside init_sg() so that importing this module
(and the rest of pit.importer) never requires a Moody's SG installation. Tests
bind a FakeSG instead of calling init_sg().
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class SG:
    sim: Any
    BulkImporter: Any
    ParameterSetImporter: Any
    DuplicateImportAction: Any
    String: Any
    File: Any


def init_sg(runtime_config: str, assembly_path: str, model_path: str,
            data_path: str, licence_path: str) -> SG:
    """Start the .NET CLR, load the SG API assembly, and build a licensed Simulation."""
    import pythonnet
    pythonnet.load("coreclr", runtime_config=runtime_config)
    if assembly_path not in sys.path:
        sys.path.append(assembly_path)
    import clr
    clr.AddReference("MoodysAnalytics.SG.API")
    from MoodysAnalytics.SG.API import (
        Simulation, BulkImporter, ParameterSetImporter, DuplicateImportAction,
    )
    from System import String
    from System.IO import File

    sim = Simulation()
    sim.InitialiseWithLicence(model_path, "", data_path, licence_path)
    return SG(
        sim=sim,
        BulkImporter=BulkImporter,
        ParameterSetImporter=ParameterSetImporter,
        DuplicateImportAction=DuplicateImportAction,
        String=String,
        File=File,
    )
```

- [ ] **Step 4: Implement `FakeSG`**

```python
# tests/importer/fakes.py
"""In-memory stand-in for the Moody's SG boundary, for tests with no .NET."""
from __future__ import annotations


class _FakeModel:
    def __init__(self, sg, name=""):
        self._sg = sg
        self.Name = name
        self._params = {}
        self._children = {}

    def AddModel(self, type_name):
        self._sg.calls.append(("model.AddModel", (self.Name, type_name)))
        child = _FakeModel(self._sg)
        return child

    def SubModel(self, name):
        self._sg.calls.append(("model.SubModel", (self.Name, name)))
        return self._children.get(name)

    def Delete(self):
        self._sg.calls.append(("model.Delete", (self.Name,)))

    def Parameter(self, name):
        self._sg.calls.append(("model.Parameter", (self.Name, name)))
        return self._params.setdefault(name, _FakeParam())

    def Output(self, output_type):
        self._sg.calls.append(("model.Output", (self.Name, output_type)))
        return _FakeOutput()

    def GetType(self):
        return type("T", (), {"Name": "Economy"})


class _FakeParam:
    def __init__(self):
        self.Value = None


class _FakeOutput:
    def AddOutput(self, output):
        return _FakeSelectedOutput()


class _FakeSelectedOutput:
    def __init__(self):
        self.NumberFormat = None


class _FakeSim:
    def __init__(self, sg):
        self._sg = sg
        self._models = {}

    def InitialiseWithLicence(self, *a): self._sg.calls.append(("sim.InitialiseWithLicence", a))
    def Load(self, p): self._sg.calls.append(("sim.Load", (p,)))
    def Create(self, n): self._sg.calls.append(("sim.Create", (n,))); return _FakeModel(self._sg, n)
    def Save(self, p): self._sg.calls.append(("sim.Save", (p,)))
    def AddModel(self, t): self._sg.calls.append(("sim.AddModel", (t,))); return _FakeModel(self._sg)
    def FindModelByName(self, n): self._sg.calls.append(("sim.FindModelByName", (n,))); return self._models.get(n)
    def FindModelByFullyQualifiedName(self, fqn):
        self._sg.calls.append(("sim.FindModelByFullyQualifiedName", (fqn,))); return _FakeModel(self._sg, fqn)
    def FindModels(self, t): self._sg.calls.append(("sim.FindModels", (t,))); return []
    def Parameter(self, n): self._sg.calls.append(("sim.Parameter", (n,))); return _FakeParam()
    def AddOutputFile(self, f): self._sg.calls.append(("sim.AddOutputFile", (f,))); return _FakeOutput()
    def RemoveOutputFile(self, f): self._sg.calls.append(("sim.RemoveOutputFile", (f,)))
    def ImportOutputFiles(self, p, a): self._sg.calls.append(("sim.ImportOutputFiles", (p, a)))


class _FakeBulkImporter:
    def __init__(self, sg): self._sg = sg
    def __call__(self): return self  # BulkImporter() construction
    def Import(self, *a): self._sg.calls.append(("BulkImporter.Import", a))
    def ImportAsync(self, *a): self._sg.calls.append(("BulkImporter.ImportAsync", a))


class _FakeParamSetImporter:
    def __init__(self, sg): self._sg = sg
    def Import(self, *a): self._sg.calls.append(("ParameterSetImporter.Import", a))


class FakeSG:
    """Mirrors pit.importer.sg_api.SG with call-recording fakes."""
    def __init__(self):
        self.calls = []
        self.sim = _FakeSim(self)
        self.BulkImporter = _FakeBulkImporter(self)
        self.ParameterSetImporter = _FakeParamSetImporter(self)
        self.DuplicateImportAction = type("Dup", (), {"Overwrite": "Overwrite"})
        self.String = lambda s: s
        self.File = type("File", (), {"ReadAllLines": staticmethod(lambda p: [])})
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/importer/test_sg_api.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pit/importer/sg_api.py tests/importer/fakes.py tests/importer/test_sg_api.py
git commit -m "feat: importer SG boundary (sg_api.init_sg) + FakeSG test double"
```

---

### Task 3: Migrate the pipeline (`pit/importer/pipeline.py`) with run(config) + injected SG

**Files:**
- Create (copy then surgically edit): `pit/importer/pipeline.py` ← `<ORIG>/RICS_BulkImport_Tool.py`
- Test: `tests/importer/test_pipeline.py`

**Interfaces:**
- Consumes: `pit.shared.config.require`, `pit.importer.sg_api.init_sg`, `pit.importer.read_rics_files.*`.
- Produces: `pipeline.run(config: dict) -> None`. Raises `pit.shared.config.ConfigError` on missing required keys. Module-level names `sim, BulkImporter, ParameterSetImporter, DuplicateImportAction, String, File, Path_Infos, multiple_GCP_types` exist (initialized to `None`/empty) and are bound by `run()` before the import work — this preserves the original functions' global-access pattern with no signature churn, and lets tests bind a FakeSG.

- [ ] **Step 1: Copy verbatim**

`cp "<ORIG>/RICS_BulkImport_Tool.py" "pit/importer/pipeline.py"`.

- [ ] **Step 2: Remove the import-time side effects (the surgical cut)**

In `pipeline.py`, DELETE the module-scope block that (per the architecture map) spans original lines ~7 and ~29–123: the `import pythonnet`, the `RICS_CONFIG_PATH`/`load_config` call, the `Path_Infos`/`multiple_GCP_types`/settings construction, the `pythonnet.load`/`sys.path.append`/`import clr`/`clr.AddReference`, the `from MoodysAnalytics.SG.API import ...`, `from System import String`, `from System.IO import File`, and the `sim = Simulation(); sim.InitialiseWithLicence(...)` lines. (Read the file and remove exactly those statements; keep all function definitions and the `from pit.importer.read_rics_files import *` — see Step 3.)

- [ ] **Step 3: Fix the Useful_functions import**

Change `from Useful_functions.Read_RICSImportFiles import *` to:
```python
from pit.importer.read_rics_files import *
```

- [ ] **Step 4: Declare the injected module-level handles**

Near the top of `pipeline.py` (after imports, before the function defs), add module globals so the existing functions resolve their names until `run()` binds them:
```python
# Bound at runtime by run() (real SG) or by tests (FakeSG). Never initialized at import.
sim = None
BulkImporter = None
ParameterSetImporter = None
DuplicateImportAction = None
String = None
File = None
Path_Infos = {}
multiple_GCP_types = {}
```

- [ ] **Step 5: Add `_bind_sg` and `run(config)`**

Append (or place before `__main__`) these functions. The body of `run()` reproduces the config-parsing the deleted module block did (copy those exact assignments from the original, now writing to the module globals), then binds the SG handles, then calls the existing `main()`:

```python
from pit.shared.config import require
from pit.importer import sg_api

REQUIRED_KEYS = [
    "paths.runtime_config",
    "paths.assembly_path",
    "paths.output_path",
    "settings.base_date",
    "settings.base_economy",
]


def _bind_sg(sg):
    """Bind SG handles into module globals so the existing functions can use them."""
    global sim, BulkImporter, ParameterSetImporter, DuplicateImportAction, String, File
    sim = sg.sim
    BulkImporter = sg.BulkImporter
    ParameterSetImporter = sg.ParameterSetImporter
    DuplicateImportAction = sg.DuplicateImportAction
    String = sg.String
    File = sg.File


def run(config: dict) -> None:
    require(config, REQUIRED_KEYS)
    global Path_Infos, multiple_GCP_types
    # --- BEGIN: config parsing copied verbatim from the original module block ---
    # (Reproduce the original assignments that built Path_Infos, multiple_GCP_types,
    #  the structured/userDefined portfolio configs, the settings flags, and the
    #  normalize_output_config(config) call — writing them to module globals where
    #  the original used module globals.)
    # --- END copied block ---
    sg = sg_api.init_sg(
        runtime_config=Path_Infos["runtime_config"],
        assembly_path=Path_Infos["assembly_path"],
        model_path=Path_Infos["model_path"],
        data_path=Path_Infos["data_path"],
        licence_path=Path_Infos["licence_path"],
    )
    _bind_sg(sg)
    main()
```

> The implementer MUST copy the exact original config-parsing statements into the marked block (do not paraphrase) so behavior is identical. `main()` and all helpers are unchanged.

- [ ] **Step 6: Update the `__main__` block**

Replace the original `if __name__ == "__main__":` block with:
```python
if __name__ == "__main__":
    import os
    from pit.shared.config import load_config
    run(load_config(os.environ.get("RICS_CONFIG_PATH", "config.yaml")))
```

- [ ] **Step 7: Write the failing tests**

```python
# tests/importer/test_pipeline.py
import importlib

import pytest

from pit.importer import pipeline
from pit.shared.config import ConfigError


def test_import_has_no_side_effects():
    importlib.reload(pipeline)  # must not load CLR / construct Simulation
    assert pipeline.sim is None  # not bound until run()


def test_run_raises_configerror_on_missing_keys():
    with pytest.raises(ConfigError) as exc:
        pipeline.run({})
    msg = str(exc.value)
    assert "paths.runtime_config" in msg
    assert "settings.base_date" in msg
```

- [ ] **Step 8: Run, verify fail→pass**

Run: `python -m pytest tests/importer/test_pipeline.py -v`
Expected: 2 passed. Also verify `python -c "import pit.importer.pipeline; print('ok')"` prints `ok` with NO pythonnet error.

- [ ] **Step 9: Commit**

```bash
git add pit/importer/pipeline.py tests/importer/test_pipeline.py
git commit -m "feat: importer pipeline.run (no import-time SG; injected sg_api boundary)"
```

---

### Task 4: Characterization tests for the pure logic functions

**Files:**
- Test: `tests/importer/test_logic.py`

**Interfaces:**
- Consumes: `pipeline.normalize_output_config`, `pipeline.convert_to_param_value`, `pipeline.sanitize_child_model_name`, and `read_rics_files`/`update_portfolio_files` helpers (per the architecture map). These are pure (no SG).

- [ ] **Step 1: Confirm signatures, then write tests**

Read the actual functions in `pipeline.py` to confirm exact signatures/behavior, then write behavior-real tests. Example skeleton (adjust to real signatures):

```python
# tests/importer/test_logic.py
from pit.importer.pipeline import (
    convert_to_param_value,
    sanitize_child_model_name,
    normalize_output_config,
)


def test_convert_to_param_value_int_float_string():
    assert convert_to_param_value(3.0) == 3 or convert_to_param_value(3.0) == "3"  # match real coercion
    assert convert_to_param_value("ABC") == "ABC"


def test_sanitize_child_model_name_cleans_invalid_chars():
    out = sanitize_child_model_name("12 Bond/X")
    assert "/" not in out and " " not in out


def test_normalize_output_config_handles_empty():
    # Confirm the real shape; assert it does not raise on minimal/empty input.
    result = normalize_output_config({"Issuer_Bond_Output": {}})
    assert result is not None


# --- "No values given => no outputs" (user requirement: lock this behavior) ---

def test_no_output_config_yields_no_outputs():
    # Missing Issuer_Bond_Output entirely -> empty outputs and selection.
    outputs, selection = normalize_output_config({})
    assert outputs == [] and selection == []


def test_blank_output_values_are_dropped():
    # Blank/whitespace output names and selections are stripped; index-aligned to min length.
    cfg = {"Issuer_Bond_Output": {
        "outputs": ["CreditClass", "  ", ""],
        "selection": [["GC"], ["  "], []],
    }}
    outputs, selection = normalize_output_config(cfg)
    # only "CreditClass" survives on the outputs side; pairing is min(len(outputs), len(selection))
    assert "CreditClass" in outputs
    assert "" not in outputs and "  " not in outputs
    assert len(outputs) == len(selection)


def test_generate_output_bho_files_empty_returns_nothing(tmp_path):
    from pit.importer.read_rics_files import generate_output_bho_files
    model_lists = {"output_data": {"GC": ["GC.IssuerA"]}}
    # No output types -> nothing generated.
    assert generate_output_bho_files(model_lists, [["All"]], [], str(tmp_path)) == ([], [])
    # No selection -> nothing generated.
    assert generate_output_bho_files(model_lists, [], ["CreditClass"], str(tmp_path)) == ([], [])
    # Confirm no .bho files were written.
    assert not any(p.suffix == ".bho" for p in tmp_path.iterdir())
```

> The implementer MUST read each function and write assertions matching its ACTUAL documented behavior (coercion rules, regex, exact return shape of `normalize_output_config`). These are characterization tests — they lock current behavior, including the user-required "no values given => no outputs" path at both the `normalize_output_config` and `generate_output_bho_files` layers. Adjust the assertions if the real return shape differs, but the empty-in/empty-out invariant MUST be asserted.

- [ ] **Step 2: Run, verify pass**

Run: `python -m pytest tests/importer/test_logic.py -v`
Expected: pass (after aligning asserts to real behavior).

- [ ] **Step 3: Commit**

```bash
git add tests/importer/test_logic.py
git commit -m "test: characterization tests for importer pure logic functions"
```

---

### Task 5: CLI entry point (`pit/importer/cli.py`)

**Files:**
- Create: `pit/importer/cli.py`
- Test: `tests/importer/test_cli.py`

**Interfaces:**
- Consumes: `pit.version.__version__`, `pit.shared.config.load_config/ConfigError`, `pit.shared.logging_setup.setup_logging`, `pit.shared.results.Result/write_results`, `pit.importer.pipeline`.
- Produces:
  - `cli.convert_excel_config_to_internal(excel_config: dict) -> dict` (mirrors `<ORIG>/excel_wrapper.py`).
  - `cli.run_import_with_config(config: dict) -> int` (setup logging next to exe, call `pipeline.run`, write `rics_import_results.json`, return 0/1).
  - `cli.main(argv: list | None = None) -> int` (`--help`/`--version`/`--json`/config-path/default).

- [ ] **Step 1: Write the failing tests**

```python
# tests/importer/test_cli.py
import json
import os

from pit.importer import cli


def test_version_returns_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "Portfolio Import Tool Importer" in capsys.readouterr().out


def test_help_returns_zero():
    assert cli.main(["--help"]) == 0


def test_missing_config_returns_one(capsys):
    assert cli.main(["Z:/no/such/config.yaml"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_excel_config_mapping_shape():
    internal = cli.convert_excel_config_to_internal({
        "runtime_config": "rc", "assembly_path": "ap", "output_path": "out",
        "base_date": "2025-12-31", "base_economy": "CAD",
    })
    assert internal["paths"]["runtime_config"] == "rc"
    assert internal["paths"]["output_path"] == "out"
    assert internal["settings"]["base_economy"] == "CAD"


def test_run_with_config_writes_results(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    monkeypatch.setattr(cli.pipeline, "run", lambda cfg: None)
    monkeypatch.setattr(cli, "_script_dir", lambda: str(out))
    config = {"paths": {"output_path": str(out / "sim.bhs")}}
    rc = cli.run_import_with_config(config)
    assert rc == 0
    with open(os.path.join(str(out), "rics_import_results.json"), encoding="utf-8") as f:
        assert json.load(f)["status"] == "success"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/importer/test_cli.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `cli.py`**

```python
# pit/importer/cli.py
"""Importer CLI — compiled into Importer.exe. Mirrors the original excel_wrapper.py
contract but uses the shared config/logging/results modules. Requires Moody's SG
at runtime (via pipeline -> sg_api); fully decoupled from the converter.
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
from pit.importer import pipeline

RESULTS_FILENAME = "rics_import_results.json"
LOG_FILENAME = "rics_import.log"


def _script_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def convert_excel_config_to_internal(excel_config: dict) -> dict:
    config = {
        "paths": {
            "runtime_config": excel_config.get("runtime_config", ""),
            "assembly_path": excel_config.get("assembly_path", ""),
            "data_path": excel_config.get("data_path", ""),
            "model_path": excel_config.get("model_path", ""),
            "licence_path": excel_config.get("licence_path", ""),
            "rics_path": excel_config.get("rics_path", ""),
            "output_path": excel_config.get("output_path", ""),
            "load_sim_path": excel_config.get("load_sim_path", ""),
        },
        "multiple_gcp_types": excel_config.get("multiple_gcp_types", {}),
        "settings": {
            "load_sim": excel_config.get("load_sim", False),
            "keep_existing_portfolios": excel_config.get("keep_existing_portfolios", False),
            "import_economies": excel_config.get("import_economies", True),
            "import_transition_matrices": excel_config.get("import_transition_matrices", True),
            "import_mpr_models": excel_config.get("import_mpr_models", True),
            "import_zscore_models": excel_config.get("import_zscore_models", True),
            "base_date": excel_config.get("base_date", "2025-06-30"),
            "base_economy": excel_config.get("base_economy", "USD"),
        },
    }
    for key in ("structured_portfolios_parameters",
                "userDefined_combined_structured_nonstructured_portfolios",
                "Issuer_Bond_Output"):
        if key in excel_config:
            config[key] = excel_config[key]
    return config


def run_import_with_config(config: dict) -> int:
    out_dir = _script_dir()
    log_path = setup_logging(os.path.join(out_dir, LOG_FILENAME))
    logger = logging.getLogger(__name__)
    try:
        pipeline.run(config)
        output_path = config["paths"]["output_path"]
        result = Result.success("Import completed successfully",
                                 output_path=output_path, log_file=log_path)
        write_results(result, out_dir, RESULTS_FILENAME)
        return 0
    except Exception as exc:
        logger.error("IMPORT FAILED: %s\n%s", exc, traceback.format_exc())
        write_results(Result.error(str(exc), log_file=log_path), out_dir, RESULTS_FILENAME)
        return 1


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        arg = argv[0]
        if arg in ("--help", "-h"):
            print("Portfolio Import Tool - Importer\n\n"
                  "Usage:\n"
                  "  Importer.exe [config.yaml]   Use a YAML config file\n"
                  "  Importer.exe --json <json>   Use a JSON config (from Excel)\n"
                  "  Importer.exe --version       Show version")
            return 0
        if arg in ("--version", "-v"):
            print(f"Portfolio Import Tool Importer {__version__}")
            return 0
        if arg == "--json":
            if len(argv) < 2:
                print("Error: --json requires a JSON string argument", file=sys.stderr)
                return 1
            return run_import_with_config(convert_excel_config_to_internal(json.loads(argv[1])))
        config_path = arg
        if not os.path.exists(config_path):
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            return 1
        try:
            config = load_config(config_path)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return run_import_with_config(config)

    default_config = os.path.join(_script_dir(), "config.yaml")
    if not os.path.exists(default_config):
        print("Error: no config provided and config.yaml not found", file=sys.stderr)
        return 1
    return run_import_with_config(load_config(default_config))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run, verify pass; full suite**

Run: `python -m pytest tests/importer/test_cli.py -v && python -m pytest -q`
Expected: 5 passed; full suite green.

- [ ] **Step 5: Commit**

```bash
git add pit/importer/cli.py tests/importer/test_cli.py
git commit -m "feat: importer CLI entry point (Importer.exe)"
```

---

### Task 6: Mock-based integration test (the no-live-SG equivalence proxy)

**Purpose:** Exercise the whole `run(config)` flow with a `FakeSG` bound and minimal RICS input files, asserting the SG call sequence and the pure side-effects (merged folders, generated BHO files). This is the importer's regression net since a live `.bhs` run is the user's manual step.

**Files:**
- Test: `tests/importer/test_run_integration.py`
- Create (test fixture builder): `tests/importer/make_rics_files.py` (synthetic minimal RICS bulk-import tree, committed — it is code, not data)

**Interfaces:**
- Consumes: `pipeline.run`, `pipeline._bind_sg`, `tests.importer.fakes.FakeSG`, `pipeline.sg_api`.

- [ ] **Step 1: Write a synthetic RICS-files generator**

`make_rics_files.py` writes a minimal but valid `granularCounterparty/GC/` tree (the RICS bulk-import CSVs `read_rics_files` expects: `1_GCP.csv`, `2_..LoadingsParameterSet.csv`, `3_ChildModelTypes.csv`, `4_ChildBond.csv`, etc.) and a `portfolio/` with `CompositePortfolio.csv` + `CompositePortfolio_HoldingsParameterSet.csv`, into a target dir. Confirm the exact expected file names/columns by reading `read_rics_files`/`process_GCP_imports` while implementing.

- [ ] **Step 2: Write the integration test**

```python
# tests/importer/test_run_integration.py
import os

from pit.importer import pipeline
from tests.importer.fakes import FakeSG
from tests.importer.make_rics_files import make_minimal_rics_tree


def test_run_with_fake_sg_drives_import_and_saves(tmp_path, monkeypatch):
    rics = tmp_path / "RICS_Files"
    make_minimal_rics_tree(str(rics))
    out_bhs = tmp_path / "out.bhs"

    config = {
        "paths": {
            "runtime_config": "x", "assembly_path": "x", "data_path": "x",
            "model_path": "x", "licence_path": "x",
            "rics_path": str(rics), "output_path": str(out_bhs), "load_sim_path": "",
        },
        "multiple_gcp_types": {},
        "settings": {
            "load_sim": False, "keep_existing_portfolios": False,
            "import_economies": True, "import_transition_matrices": False,
            "import_mpr_models": False, "import_zscore_models": False,
            "base_date": "2025-12-31", "base_economy": "CAD",
        },
        "Issuer_Bond_Output": {},
    }

    fake = FakeSG()
    # Bypass the real CLR init: bind the fake instead of calling sg_api.init_sg.
    monkeypatch.setattr(pipeline.sg_api, "init_sg", lambda **kw: fake)

    pipeline.run(config)

    names = [c[0] for c in fake.calls]
    assert "sim.Create" in names          # new sim created (load_sim False)
    assert "BulkImporter.Import" in names or "BulkImporter.ImportAsync" in names
    assert "sim.Save" in names            # output written
    # Save called with the configured output path
    save_args = [c[1] for c in fake.calls if c[0] == "sim.Save"]
    assert any(str(out_bhs) in str(a[0]) for a in save_args)
```

> The implementer must align config/fixtures to what `run()` actually requires so the flow reaches `sim.Save` without a live SG. If a real SG-only code path blocks the fake (e.g. a `.NET`-typed return used in arithmetic), extend `FakeSG` minimally to return a sensible value and note it — do NOT change pipeline logic.

- [ ] **Step 3: Run, verify pass; full suite**

Run: `python -m pytest tests/importer/test_run_integration.py -v && python -m pytest -q`
Expected: integration test passes; full suite green.

- [ ] **Step 4: Commit**

```bash
git add tests/importer/test_run_integration.py tests/importer/make_rics_files.py
git commit -m "test: importer mock-SG integration test (no live SG)"
```

---

## Self-Review

**Spec coverage (Importer slice, spec §4/§7/§8 Part 3):**
- `pit/importer/` package with `bho.py`, `read_rics_files.py` (verbatim) — Task 1. ✓
- `pit/importer/sg_api.py` — single mockable SG boundary; no import-time CLR — Task 2. ✓
- `pit/importer/pipeline.py` = `run(config)` refactor of `RICS_BulkImport_Tool.py`, no import-time side effects — Task 3. ✓
- Pure-logic characterization tests — Task 4. ✓
- `pit/importer/cli.py` entry point (Importer.exe), shared modules, `rics_import_results.json` — Task 5. ✓
- Mock-SG integration test as the no-live-SG regression net — Task 6. ✓
- Decoupling / own results filename / no shared runtime state — Tasks 2,3,5. ✓

**Placeholder scan:** New code (`sg_api.py`, `FakeSG`, `cli.py`, test skeletons) is given in full. The two vendored modules and the pipeline body are specified as "copy verbatim + these exact edits" (a migration, not new code). Tasks 1/4/6 explicitly require the implementer to confirm real signatures/output and align assertions — these are flagged, not hidden placeholders, because the exact column names / coercion rules live in large original files; the verification (tests must pass against real behavior) is concrete.

**Type consistency:** `sg_api.SG` fields match the handles `pipeline._bind_sg` binds and the names the original functions reference (`sim, BulkImporter, ParameterSetImporter, DuplicateImportAction, String, File`). `FakeSG` exposes the same attribute names. `run_import_with_config` uses `pipeline.run`, `Result.success/error`, `write_results(result, out_dir, filename)` — matching Plan-1 signatures and the converter's cli pattern.

**Risk note (carried to execution):** Task 3 is the highest-risk task — a surgical refactor of a 1,592-line SG-coupled file. The injected-module-globals approach keeps function signatures unchanged (low churn) at the cost of mutable module state (acceptable for a faithful migration; the state is injected, never created at import). The mock-SG integration test (Task 6) is the safety net but cannot prove `.bhs` output correctness — that remains the user's manual live-SG acceptance step. If the FakeSG cannot carry the flow to `sim.Save` because a real SG-typed value is used in non-trivial logic, extend FakeSG (never the pipeline) and record it.

**Dependency on Plan 1/2:** reuses `pit.shared` (config/logging/results) — delivered and green; pandas pin `<3` already in `pyproject` (Plan 2 fix) and applies here too.
