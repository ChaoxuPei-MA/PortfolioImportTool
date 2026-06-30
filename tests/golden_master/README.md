# tests/golden_master/README.md

Golden-master baselines freeze the ORIGINAL converter's output so the migrated
`pit.converter` can be proven equivalent.

## What is committed vs not
- Committed: `tree_hash.py`, `compare.py`, `capture_converter.py`, this README, the tests.
- NOT committed (gitignored): `tests/golden/`, any sample data, the golden output tree.

## Equivalence is numeric-tolerant, not byte-exact
Floating-point summation order differs by ~1e-16 across pandas/numpy patch
versions, so two numerically-identical runs can differ in the last digit of a
float column. `compare.py::compare_trees` therefore compares float columns within
a tolerance (`float_atol`, default 1e-9) while requiring exact equality for every
non-float column and every non-CSV file. The timestamped summary file is ignored.
(`tree_hash.py` byte-hashing remains for non-numeric uses and unit tests.)

## IMPORTANT: pandas version
The converter relies on pandas 2.x `groupby().apply()` semantics (pandas 3.0
removed group-key inclusion). Run the original tool and the equivalence check
with **pandas 2.x** (the project pins `pandas>=2.2,<3`). Use the project venv.

## Capture the golden tree (run once, locally)
The simplest golden tree is the output of the working original — e.g. run the
released `RICSConverter.exe` (self-contained) on a config whose `output_path`
points at a scratch dir, OR reuse an existing `RICS_Files/` the original produced.
Keep it OUTSIDE git.

```powershell
& "C:\...\RICS_BulkImportFiles_Converter\dist\RICSConverter.exe" "C:\scratch\orig_config.yaml"
# -> golden tree at the config's output_path, e.g. C:\scratch\orig_out
```

(`capture_converter.py` can instead run the original `main.py` directly, but that
source needs Python 3.12+ to parse — the exe avoids that.)

## Verify the migration (Plan 2)
Prove the migrated converter matches the golden tree:
```powershell
$env:PIT_GOLDEN     = "1"
$env:PIT_GOLDEN_DIR = "C:\scratch\orig_out"                 # original converter's output tree
$env:PIT_CONVERT_SAMPLE_CONFIG = "C:\scratch\convert_config.yaml"  # output_path -> a fresh scratch dir
.\.venv\Scripts\python -m pytest tests/converter/test_golden_equivalence.py -v
```
PASS = the migrated converter reproduces the original's output (exact for all
integer/string data, within 1e-9 for floats, summary excluded).

The importer baseline (Plan 3) will be captured analogously on the parsed-config
+ generated-YAML with the SG boundary mocked — added when Plan 3 is planned.
