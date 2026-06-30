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
