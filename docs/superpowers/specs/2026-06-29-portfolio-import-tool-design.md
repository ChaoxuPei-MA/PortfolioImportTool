# PortfolioImportTool — Design Spec

**Date:** 2026-06-29
**Status:** Draft for review
**Author:** brainstormed with Claude Code

---

## 1. Purpose

Merge two existing, related tools into one cohesive, robust, extensible project named
**PortfolioImportTool**, and produce a **single Excel workbook**
(`Portfolio_Import_Tool.xlsm`) in `PortfolioImportTool\excelTool` with **two tabs**:

- **Convert** — transforms simplified client/user data into RICS bulk-import CSV files.
  (Source: `RICS_BulkImportFiles_Converter`.)
- **Import** — imports RICS bulk-import CSV files into Moody's SG via the .NET API and
  produces a `.bhs` simulation. (Source: `RICS_API_BulkImport`.)

The new project supersedes the *core pipeline* of both source projects. Auxiliary code
(CMHC pipeline, `compare_datasets`, `process_gcorr`, `Selective_Outputs`, one-off analysis
scripts) is **out of scope** and stays in the original repos.

### Overriding constraint: no behavior regressions

The user's primary requirement is that merging and refactoring introduce **no bugs**. The
entire plan is built around **characterization (golden-master) testing**: the current
behavior of each original tool is captured on fixed inputs *before* any refactor, and every
refactor is proven to reproduce that output exactly.

---

## 2. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | **Core pipeline only** (Converter + Importer). Auxiliary scripts excluded. |
| 2 | Executables | **Two separate exes** — `Converter.exe` (no SG dependency), `Importer.exe` (requires Moody's SG + .NET + license). |
| 3 | Excel target | **New workbook** `Portfolio_Import_Tool.xlsm` built into `PortfolioImportTool\excelTool`, with two config tabs + unified VBA project. Existing `RICS_Tools(10.5)_Final_*.xlsm` left untouched. |
| 4 | Validation depth | **Tests + static checks, no live SG.** Converter validated end-to-end; Importer validated structurally with the SG boundary mocked. Live `.bhs` run is the user's manual acceptance step. |
| 5 | Naming | Umbrella **"Portfolio Import Tool"**, stages **Convert/Import**, `PIT_` prefix throughout. |
| 6 | xlsm build | **Auto-built via Excel automation** (win32com). VBA lives as version-controlled `.bas`; `.xlsm` is a reproducible build artifact. |
| 7 | Python package name | `pit` |
| 8 | Test data | **No data committed.** Fixtures/golden snapshots are gitignored and generated locally by a committed deterministic generator script. |

---

## 3. Tool independence (key robustness property)

The two tools are **fully decoupled**. There is no shared runtime state and neither tab
depends on the other having run:

- Each tab runs **its own executable** and writes **its own results file**
  (`PIT_Convert_Results` sheet ← convert results JSON; `PIT_Import_Results` sheet ←
  import results JSON). Both results files use the **same JSON schema**, but they are
  separate files. "Shared contract" ≠ "shared file."
- The Import tab consumes a `rics_path` pointing at RICS bulk-import CSVs. Those CSVs may
  come from our Converter, a previous run, or be supplied directly. The Importer never
  reads converter results or requires a converter run.

**Supported usage modes:** Convert only · Import only · Convert then Import. The VBA must
make this explicit (comments + independent macros `RunConvert` / `RunImport`).

---

## 4. Target project structure

```
PortfolioImportTool/
├── pyproject.toml
├── README.md
├── .gitignore                       # ignores tests/fixtures/, tests/golden/, dist/, build artifacts
├── pit/                             # installable package ("Portfolio Import Tool")
│   ├── __init__.py
│   ├── version.py
│   ├── shared/                      # de-duplicated core shared by both tools
│   │   ├── __init__.py
│   │   ├── config.py                # schema-validated YAML load with precise errors
│   │   ├── results.py               # single results-JSON contract (status/message/elapsed/...)
│   │   ├── logging_setup.py
│   │   └── io_utils.py
│   ├── converter/
│   │   ├── __init__.py
│   │   ├── cli.py                   # entry point for Converter.exe
│   │   ├── pipeline.py              # was main.py — refactored to run(config) -> Result
│   │   ├── summary.py               # summary-file writing (extracted from main.py)
│   │   ├── processors/              # was Userful_Functions/ (typo fixed)
│   │   │   ├── __init__.py
│   │   │   ├── registry.py          # data_type -> processor class (replaces if/elif chains)
│   │   │   ├── userdata.py
│   │   │   ├── granular.py          # GC / GCCRE / GCRETAIL
│   │   │   ├── agency_mbs.py
│   │   │   ├── portfolio.py
│   │   │   ├── convert_to_rics.py
│   │   │   └── update_import_files.py
│   │   └── data/                    # bundled MoodysInternalData (reference data, not test data)
│   └── importer/
│       ├── __init__.py
│       ├── cli.py                   # entry point for Importer.exe
│       ├── pipeline.py              # was RICS_BulkImport_Tool.py — run(config) -> Result
│       └── sg_api.py                # thin wrapper over the Moody's SG .NET boundary (mockable)
├── excel/                           # VBA source + builder (version-controlled)
│   ├── PortfolioImportTool.bas      # ONE unified VBA module (shared core + Convert + Import)
│   └── build_workbook.py            # win32com builder -> excelTool\Portfolio_Import_Tool.xlsm
├── excelTool/                       # build output: Portfolio_Import_Tool.xlsm (deliverable)
├── build/
│   ├── converter.spec               # PyInstaller
│   ├── importer.spec
│   └── build_all.bat
├── configs/
│   ├── convert.example.yaml
│   └── import.example.yaml
├── tests/
│   ├── make_fixtures.py             # committed; generates synthetic inputs deterministically
│   ├── fixtures/                    # gitignored (generated)
│   ├── golden/                      # gitignored (captured golden masters)
│   ├── shared/  converter/  importer/  excel/
└── docs/
    ├── USER_GUIDE.md                # merged guide for both tabs
    └── superpowers/specs/           # this spec
```

---

## 5. Naming map

| Concept | Old | New |
|---|---|---|
| Workbook | `RICS_Tools_v1.xlsm` / `RICS_Tools.xlsm` | `Portfolio_Import_Tool.xlsm` |
| Convert config sheet | `RICS_Converter_Config` | `PIT_Convert_Config` |
| Import config sheet | `RICS_Config` | `PIT_Import_Config` |
| Convert results sheet | `RICS_Converter_Results` | `PIT_Convert_Results` |
| Import results sheet | `RICS_Results` | `PIT_Import_Results` |
| Converter exe | `RICSConverter.exe` | `Converter.exe` |
| Importer exe | `RICSImportTool.exe` | `Importer.exe` |
| Convert macro | `RunRICSConverter` | `RunConvert` |
| Import macro | `RunRICSImport` | `RunImport` |
| Processor code folder | `Userful_Functions/` (typo) | `pit/converter/processors/` |

---

## 6. Excel workbook design

Single `.xlsm`, one unified VBA module. A **shared VBA core** (workbook-path / OneDrive
resolution, temp-YAML writing, exe execution, results-JSON parsing, results-sheet rendering)
is parameterized by a per-tool **descriptor** (sheet names, exe path row, row map, YAML
builder callback). This removes the ~90% duplication between the two original ~1500-line
addins.

Public macros: `RunConvert`, `RunImport`, `CreateConfigSheets` (builds both tabs),
`ViewConvertLog`, `ViewImportLog`, `ViewConvertSummary`.

### 6.1 Convert tab (`PIT_Convert_Config`) — section order

1. **Tool Configuration** — exe path, results JSON path, log path
2. **Paths** — Data Path, Output Path
3. **General Settings** — Start Date, GCorr Corporate Version, RICS Version
4. **Data Types to Process** — granularCounterparty folder list, portfolio enable
5. **Advanced Settings** — *(renamed from "Parameter Settings")* ImpliedCreditClass default,
   CreditClass default, LGD interpolation, GCorr RSQ/country/industry flags, RSQ defaults,
   groupby settings
6. **Instructions**

### 6.2 Import tab (`PIT_Import_Config`) — section order (reordered per user)

1. **Tool Configuration** — exe path, results JSON path, log path
2. **Paths** — runtime config, assembly, data, model, licence, rics_path, output, load_sim
3. **Settings** — *(moved up, directly under Paths)* load_sim, keep_existing_portfolios,
   import flags (economies / transition matrices / MPR / zscore), base_date, base_economy
4. **Merge Data** — *(renamed from "Multiple GCP Types")* base-folder → sub-folders to merge
5. **Outputs** — *(renamed from "Issuer/Bond Output")* output types × GCP-type selection
6. **Structured Portfolios** — type / enabled / currency / weight definition
7. **User Defined Portfolios** — combined portfolio name / portfolios to merge / currency / weight
8. **Instructions**

> Row-constant maps in the VBA must be updated to match these new orders. Because section
> ordering changes, the row indices are regenerated from scratch rather than reused.

---

## 7. Robustness & flexibility improvements

Each change has a concrete justification:

1. **Eliminate import-time execution.** `main.py` currently runs the entire pipeline at
   module import and pulls config from an env var (`RICS_CONFIG_PATH`). This is untestable
   and fragile. → Refactor into `pipeline.run(config) -> Result`, invoked by `cli.py`.
   This single change unlocks all testing.
2. **Shared schema-validated config** (`pit/shared/config.py`) with precise, actionable
   error messages, replacing scattered `config['key']` KeyErrors. Both tools validate up
   front and fail clearly.
3. **Processor registry** (`converter/processors/registry.py`) replacing the
   `if data_type=='AGENCYMBS' / elif data_type in ['GC','GCCRE','GCRETAIL']` chains. New
   data types register a processor class — orchestration code is not edited. This is the
   "flexible for future extension" lever.
4. **One results-JSON contract** (`pit/shared/results.py`): `status, message, elapsed,
   output_path, summary_file, log_file`. Both exes emit it; the VBA has one parser. (Each
   run still writes its own file — see §3.)
5. **One shared VBA core** parameterized per tool (see §6).
6. **Centralized logging** (`pit/shared/logging_setup.py`) used by both tools.
7. **Real test suite** under `tests/` with pytest.

---

## 8. Decomposition into independent parts

Each part is a self-contained unit with its own tests and a **review checkpoint before the
next begins**. Dependency order: 0 → 1 → {2, 3} → 4 → 5 → 6 → 7 (2 and 3 are mutually
independent).

- **Part 0 — Scaffold + shared core.** Package skeleton, `pyproject`, `.gitignore`,
  `shared/` (config, results, logging, io_utils), pytest harness.
  *Validate:* shared-module unit tests green.

- **Part 1 — Capture golden masters.** Commit `tests/make_fixtures.py` (deterministic
  synthetic inputs). Run the **original** Converter and Importer on those fixtures; snapshot
  outputs into `tests/golden/` (gitignored): Converter → generated CSV tree; Importer →
  parsed-config object + generated YAML (SG boundary mocked). This baseline is captured
  **before** refactoring.
  *Validate:* snapshots reproducible from the generator + original code.

- **Part 2 — Converter backend.** Migrate core into `pit/converter/`, refactor to
  `run(config)`, introduce processor registry, extract summary writing.
  *Validate:* unit tests + **end-to-end convert on fixtures, diffed byte-for-byte against
  Part-1 golden CSVs.**

- **Part 3 — Importer backend.** Migrate core into `pit/importer/`, refactor to
  `run(config)`, isolate the SG boundary in `sg_api.py`.
  *Validate:* config/YAML parsing parity vs golden master; SG-call arguments asserted via a
  mocked `sg_api`. No live SG.

- **Part 4 — Unified VBA module.** Shared core + Convert/Import descriptors, new section
  orders/names (§6), `PIT_` naming, independence comments.
  *Validate:* for identical inputs, generated YAML byte-compared to what each **original**
  addin emitted (captured as VBA golden fixtures).

- **Part 5 — Workbook auto-builder.** `excel/build_workbook.py` (win32com) → produces
  `Portfolio_Import_Tool.xlsm` in `PortfolioImportTool\excelTool`, imports the `.bas`,
  builds both tabs.
  *Validate:* build runs; reopen workbook and assert sheets, key cells, buttons, and data
  validations exist; round-trip a sample config.

- **Part 6 — PyInstaller specs + `build_all.bat`.** Two specs producing `Converter.exe`
  and `Importer.exe`.
  *Validate:* both build; `Converter.exe` smoke-run on fixtures; `Importer.exe`
  argument-parse / dry path check.

- **Part 7 — Merged docs + final integration pass.** `USER_GUIDE.md` covering both tabs and
  all three usage modes; end-to-end Convert run; final review.

---

## 9. Validation strategy (how "no bugs" is enforced)

- **Golden-master diffing** (Part 1) is the backbone: freeze current behavior, then prove
  it unchanged after every refactor.
- **TDD per part** — tests precede refactored implementation.
- **Mocked SG boundary** (`sg_api.py`) makes the Importer fully testable without a Moody's
  install. The live `.bhs` run is the user's manual acceptance step.
- **Review checkpoint after each part** — defects are caught locally; nothing cascades.

---

## 10. Out of scope

- CMHC liability pipeline, `compare_datasets`, `process_gcorr`, `Selective_Outputs`,
  one-off analysis scripts.
- Live Moody's SG import execution by the agent.
- Mac/Linux support (Windows-only, consistent with both source tools).
- Committing any data (real or sample) to version control.

---

## 11. Open questions / assumptions

- Assumes the synthetic fixtures from `make_fixtures.py` exercise enough of each processor
  to make golden-master diffs meaningful; if a code path needs richer input, the generator
  is extended (still synthetic, still gitignored).
- Assumes Excel + Python `win32com` are available on the build machine (confirmed Windows
  environment).
- Assumes `PortfolioImportTool` becomes its own git repository.
