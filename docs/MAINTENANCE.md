# Maintaining & Releasing (keeping the build artifacts and `ToUser/` in sync)

**Key rule:** the shipped artifacts are **built from source** and are gitignored. If you
change source, you must **rebuild** the affected artifacts and **re-assemble `ToUser/`**,
or the package you share will be stale.

## Source → artifact map

| Artifact (gitignored) | Built from | How to build |
|---|---|---|
| `excelTool\Portfolio_Import_Tool.xlsm` | `excel\PortfolioImportTool.bas` | `excel\build_workbook.py` (needs Excel + `AccessVBOM=1`) |
| `dist\Converter.exe` | `pit\converter\**`, `pit\shared\**`, `MoodysInternalData\` (bundled), `build\converter.spec` | `build\converter.spec` |
| `dist\Importer.exe` | `pit\importer\**`, `pit\shared\**`, `build\importer.spec` | `build\importer.spec` |
| `dist\Pipeline.exe` | `scripts\run_pipeline.py`, `pit\**`, `MoodysInternalData\`, `build\pipeline.spec` | `build\pipeline.spec` |
| `ToUser\` | all of the above + `build\touser\**` (UserGuide, config templates) | `build\make_touser.py` |

## If you change X → rebuild Y (then re-assemble ToUser)

| You changed… | Rebuild | Then |
|---|---|---|
| `pit\shared\**` | Converter.exe **and** Importer.exe **and** Pipeline.exe | re-run `make_touser.py` |
| `pit\converter\**` (incl. `processors\`) | Converter.exe + Pipeline.exe | re-run `make_touser.py` |
| `pit\importer\**` (incl. `sg_api.py`) | Importer.exe + Pipeline.exe | re-run `make_touser.py` |
| `scripts\run_pipeline.py` | Pipeline.exe | re-run `make_touser.py` |
| `excel\PortfolioImportTool.bas` | the workbook (`build_workbook.py`) | re-run `make_touser.py` |
| `build\touser\**` (UserGuide / config templates) | — | re-run `make_touser.py` only |
| `MoodysInternalData\` (reference data) | Converter.exe + Pipeline.exe (re-bundle) | re-run `make_touser.py` |

> `build\build_all.bat` rebuilds all three exes **and** runs `make_touser.py` — so after
> any `pit\` or `scripts\` change, running `build\build_all.bat` is the one-shot refresh
> for the exes + package. The **workbook** is separate: rebuild it with
> `excel\build_workbook.py` whenever you change the `.bas` (and before assembling ToUser,
> since `make_touser.py` copies the workbook into the package).

## Full release sequence (from the project root, using the venv)

```powershell
# 1. Tests must pass
.\.venv\Scripts\python -m pytest -q

# 2. Rebuild the workbook (only needed if the .bas changed)
#    Enable Excel VBA-project access, build, then revert it:
powershell -NoProfile -Command "Set-ItemProperty 'HKCU:\Software\Microsoft\Office\16.0\Excel\Security' -Name AccessVBOM -Type DWord -Value 1"
.\.venv\Scripts\python excel\build_workbook.py
powershell -NoProfile -Command "Remove-ItemProperty 'HKCU:\Software\Microsoft\Office\16.0\Excel\Security' -Name AccessVBOM -ErrorAction SilentlyContinue"

# 3. Build all three exes AND assemble ToUser\
build\build_all.bat

# 4. (optional) Validate Converter.exe output vs the original tool
.\.venv\Scripts\python scripts\compare_outputs.py <original_output_dir> ToUser\output

# 5. Zip ToUser\ and share it
```

## Notes

- **Always use the venv** (`.\.venv\Scripts\python` / `pyinstaller`) — it has the pinned
  `pandas 2.x`. The global interpreter (pandas 3.x) breaks the converter.
- **`AccessVBOM`** is only needed while building the workbook; revert it afterward.
- Artifacts (`dist\`, `/ToUser\`, `excelTool\*.xlsm`) and local data
  (`UserData\`, `MoodysInternalData\`, `output\`, `configs\*.local.yaml`) are **gitignored**.
  Only sources are committed, so the build is fully reproducible on a clean clone
  (after you supply `MoodysInternalData\` locally — it is not committed).
- **Publishing:** commit source changes, then `git push`. Never commit data, licences, or
  the built artifacts.
- **Versioning:** bump `pit/version.py` when releasing a new build; the exes report it via
  `--version`.
