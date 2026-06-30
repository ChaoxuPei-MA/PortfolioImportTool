# Portfolio Import Tool

Convert client/user data into RICS bulk-import files, and import those files into
Moody's SG to produce a `.bhs` simulation. The two stages are independent — run
either one alone, or both in sequence.

| Stage | Command (module) | What it does | Needs Moody's SG? |
|-------|------------------|--------------|-------------------|
| **Convert** | `pit.converter.cli` | user data → RICS bulk-import CSVs | No |
| **Import**  | `pit.importer.cli`  | RICS bulk-import CSVs → `.bhs` simulation | **Yes** |

> Status: the Python backends (Convert + Import) are complete and tested. The
> single two-tab Excel workbook and the standalone `.exe`s are built on top of
> these and are in progress — this README covers running the Python tools today.

---

## 1. Requirements

- **Windows** (the Import stage uses Moody's SG .NET assemblies).
- **Python 3.11+**.
- **pandas 2.x** — the converter relies on pandas 2.x `groupby().apply()` behavior
  that pandas 3.0 removed. The project pins `pandas>=2.2,<3`; **use the project
  venv** (below) so you get the right version. Running with a global pandas 3.x
  install will fail with `KeyError: 'Name'`.
- **Import stage only:** a working Moody's SG installation + a valid `.licx`
  licence file. (Not needed for Convert.)

---

## 2. One-time setup

Open a terminal **in the project root** (`…\PortfolioImportTool`). Create and
populate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Verify pandas is 2.x:

```powershell
.\.venv\Scripts\python -m pip show pandas
```

> ⚠️ Always invoke Python as `.\.venv\Scripts\python` (not plain `python`) so you
> use the venv with the correct pandas.

---

## 3. Project structure

```
PortfolioImportTool/
├── pit/
│   ├── shared/        config loading, results JSON, logging (shared by both tools)
│   ├── converter/     Convert stage (cli.py, pipeline.py, processors/)
│   └── importer/      Import stage (cli.py, pipeline.py, sg_api.py, ...)
├── configs/
│   ├── convert.example.yaml   committed example
│   ├── convert.local.yaml     your local Convert config (gitignored)
│   └── import.local.yaml      your local Import config (gitignored)
├── scripts/           helper scripts (e.g. compare_outputs.py)
├── tests/             unit + characterization + golden-master tests
├── docs/              specs, plans, this guide
├── UserData/          your input data — optional, gitignored (see §4)
├── output/            generated RICS files / .bhs (gitignored)
└── .venv/             virtual environment (gitignored)
```

Your data, reference data, and outputs are **gitignored** and never committed
(`UserData/`, `MoodysInternalData/`, `RICS_Files/`, `output/`, `configs/*.local.yaml`).

---

## 4. Stage 1 — Convert (user data → RICS files)

### 4a. Lay out your UserData

Put it **anywhere** — including inside the project (e.g. `PortfolioImportTool\UserData\`,
which is gitignored). You point the config at it via `converter_paths.data_path`
(see §4c): an **absolute path**, or a **relative path** resolved from where you run
the command (so `data_path: "UserData"` works when you run from the project root).
It must contain two subfolders:

```
UserData\
├── granularCounterparty\
│   ├── GC\          GC_Issuers.csv, GC_IndustryFactors.csv, GC_Instruments.csv, GC_LGDs.csv, GC_Cashflows.csv
│   ├── GCCRE\       GCCRE_Issuers.csv, GCCRE_GeographyPropertyFactors.csv, GCCRE_Instruments.csv, GCCRE_LGDs.csv, GCCRE_Cashflows.csv
│   └── AgencyMBS\   AgencyMBS_Issuers.csv, AgencyMBS_Instruments.csv, AgencyMBS_Laggard.csv
└── portfolio\
    ├── Portfolios.csv
    └── Holdings.csv
```

- File naming is `<Folder>_<Type>.csv`. Include only the subfolders you have, and
  list them in the config's `converter_data_types.granular`.
- A known-good template lives at
  `..\RICS_BulkImportFiles_Converter\UserData` — copy it and swap in your data.

### 4b. Get the reference data (MoodysInternalData)

This folder holds GCorr factors, RICS format files, and mapping tables (Moody's
reference data, not your data). It is **not** in the repo. Point the config at an
existing copy, e.g. `..\RICS_BulkImportFiles_Converter\MoodysInternalData`, or copy
that folder into the project.

### 4c. Configure

Edit **`configs\convert.local.yaml`** and set the paths marked `EDIT THESE`:

- `converter_paths.data_path` → your `UserData` folder
- `converter_paths.output_path` → where to write results (e.g. `…\PortfolioImportTool\output`)
- `moodys_internal_data` → the `MoodysInternalData` folder
- `converter_data_types.granular` → your actual subfolder names
- `start_date`, `RICS_version`, `GCorr_Corporate_version` → as needed

### 4d. Run

```powershell
.\.venv\Scripts\python -m pit.converter.cli configs\convert.local.yaml
```

Success ends with `RICS bulk import files generated successfully`.

### 4e. Check the output

- Converted files under your `output_path`:
  `granularCounterparty\GC\1_GCP.csv …`, `…\GCCRE\…`, `…\AgencyMBS\…`,
  `portfolio\CompositePortfolio.csv`, plus `RICS_Format_Converter_Summary.txt`.
- Run status/log: `pit\converter\rics_converter_results.json` and
  `pit\converter\rics_converter.log`.

---

## 5. Stage 2 — Import (RICS files → `.bhs`)  *(requires Moody's SG)*

### 5a. Configure

Edit **`configs\import.local.yaml`** and set the paths marked `EDIT THESE`:

- `paths.runtime_config` / `assembly_path` / `data_path` / `model_path` → your
  Moody's SG install (the version folder may differ from `10.5.0`)
- `paths.licence_path` → your `.licx` file
- `paths.rics_path` → the **Convert stage's `output\` folder** (must contain
  `granularCounterparty\` and `portfolio\`) — the two stages chain here
- `paths.output_path` → the `.bhs` file to write
- `settings.base_date` / `base_economy` → your simulation base

Notes:
- Issuer/bond outputs default to **none** (`Issuer_Bond_Output.outputs: []`,
  `selection: []`). If no values are given, no outputs are added. Uncomment the
  example to add them.
- `multiple_gcp_types`, `structured_portfolios_parameters`, and load-existing-sim
  options are off by default; see the comments in the file.

### 5b. Run

```powershell
.\.venv\Scripts\python -m pit.importer.cli configs\import.local.yaml
```

### 5c. Check the output

- The `.bhs` at `paths.output_path`. Open it in Moody's SG to confirm it's correct.
- Run status/log: `pit\importer\rics_import_results.json` and
  `pit\importer\rics_import.log`.

---

## 6. Full pipeline (both stages)

```powershell
cd "C:\Users\peic\OneDrive - Moody's\Documents\POCs\Projects\PortfolioImportTool"

# 1) Convert your data into RICS files
.\.venv\Scripts\python -m pit.converter.cli configs\convert.local.yaml

# 2) Import those RICS files into SG -> .bhs   (needs live Moody's SG)
.\.venv\Scripts\python -m pit.importer.cli configs\import.local.yaml
```

---

## 7. Running the tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

All tests run **without** a Moody's SG install (the SG boundary is mocked). The
opt-in converter golden-master equivalence test is skipped unless configured —
see `tests\golden_master\README.md` to run it.

---

## 8. Validate output against the original tool

To prove the migrated converter matches the original `RICSConverter.exe`, compare
their output trees with `scripts\compare_outputs.py`. It is **numeric-tolerant**:
exact for every integer/string value and non-CSV file, and within a float
tolerance (default `1e-9`) for float columns — because last-bit floating-point
summation noise (~1e-16) differs across pandas/numpy patch versions and is not a
data difference. The timestamped summary file is ignored by default.

```powershell
# 1) Produce the ORIGINAL output once (self-contained exe; same config as ours):
& "C:\...\RICS_BulkImportFiles_Converter\dist\RICSConverter.exe" "C:\...\orig_config.yaml"
#    -> writes to that config's output_path, e.g. C:\scratch\orig_out

# 2) Produce OUR output:
.\.venv\Scripts\python -m pit.converter.cli configs\convert.local.yaml   # -> .\output

# 3) Compare:
.\.venv\Scripts\python scripts\compare_outputs.py "C:\scratch\orig_out" output
```

Exit code `0` = equivalent; `1` = real differences (printed). It also prints a
byte-level breakdown and, for any differing CSV, the max float delta per file —
so you can see exactly what changed. Use `--atol <value>` to tighten/loosen the
float tolerance, or `--include-summary` to also diff the summary file.

> A previous run on the sample data reported `EQUIVALENT`: 30/32 files
> byte-identical, the 2 factor-loadings files within `3.05e-16`, summary excluded.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `KeyError: 'Name'` during Convert | You ran with pandas 3.x. Use `.\.venv\Scripts\python` (pandas 2.x). |
| `MoodysInternalData ... not found` | Set `moodys_internal_data` to a folder containing `RICS_BulkImportFiles_Formats.csv`. |
| `Config file not found` | Check the config path argument; run from the project root. |
| `Missing or empty required config keys` | Fill the listed keys in your `.local.yaml`. |
| Import fails at SG init / `pythonnet` | Moody's SG not installed or paths wrong. Convert works without SG; Import requires it. |
| Status `error` but no detail | Open the matching `pit\<stage>\rics_*.log`. |

`--help` and `--version` are available on both tools:

```powershell
.\.venv\Scripts\python -m pit.converter.cli --help
.\.venv\Scripts\python -m pit.importer.cli --version
```

---

## 10. How it works (brief)

- `pit/shared/` provides one config loader/validator, one results-JSON contract,
  and shared logging used by both stages.
- `pit/converter/` migrates the original RICS converter into a testable
  `run(config)` with a processor registry; output is byte-for-byte equivalent to
  the original tool (verified via golden-master comparison).
- `pit/importer/` isolates all Moody's SG / .NET access behind `sg_api.py`, so the
  whole import flow is unit-testable with the SG boundary mocked; the live `.bhs`
  is produced only when run against a real SG install.

See `docs\superpowers\specs\` and `docs\superpowers\plans\` for the full design.
