# PIT Executables (PyInstaller) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build two standalone Windows executables into `dist/`:
- `dist/Converter.exe` — freezes `pit.converter.cli`, **bundles MoodysInternalData**; runs with no Python/SG install.
- `dist/Importer.exe` — freezes `pit.importer.cli` with `pythonnet`/`clr` bundled; needs a Moody's SG install at runtime (SG assemblies are NOT bundled — found via `assembly_path`).

**Architecture:** Thin entry scripts import each `cli.main`. PyInstaller `.spec` files (onefile, console) live in `build/`. Converter is validated end-to-end (run the exe on real data, compare output to the golden oracle with `scripts/compare_outputs.py`). Importer is smoke-validated with `--version` (no SG needed — `clr` loads lazily in `sg_api.init_sg`).

**Tech Stack:** PyInstaller, project venv (pandas 2.x, pywin32 already present), pythonnet. Windows.

## Global Constraints

- Build with the **project venv**: `.\.venv\Scripts\pyinstaller ...` (pandas 2.x). Never the global interpreter.
- Output exe names EXACTLY `Converter.exe` and `Importer.exe`, in `dist/` (the workbook's default exe paths are `.\dist\Converter.exe` / `.\dist\Importer.exe`). `dist/` and `build/` (PyInstaller work dir) are gitignored.
- Converter bundles the project's `MoodysInternalData/`; `resolve_moodys_data` already checks `sys._MEIPASS`. Do NOT bundle UserData/RICS/output (runtime inputs).
- Importer: `pythonnet` + `clr` as hidden imports; do NOT bundle SG assemblies or a licence.
- `.bas`/VBA and Python backends are unchanged by this plan.
- Success gates: Converter.exe reproduces the golden output (`compare_outputs.py` → EQUIVALENT); Importer.exe `--version` exits 0.

---

### Task 1: PyInstaller setup + entry scripts

**Files:**
- Modify: `pyproject.toml` (add `pyinstaller` to the `dev` extra)
- Create: `build/converter_main.py`, `build/importer_main.py`

- [ ] **Step 1: Add PyInstaller to dev deps + install**

Edit `pyproject.toml` dev extra to `dev = ["pytest>=7.4", "pyinstaller>=6.0"]`. Then: `.\.venv\Scripts\python -m pip install pyinstaller`.

- [ ] **Step 2: Entry scripts**

```python
# build/converter_main.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pit.converter.cli import main
if __name__ == "__main__":
    sys.exit(main())
```

```python
# build/importer_main.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pit.importer.cli import main
if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml build/converter_main.py build/importer_main.py
git commit -m "build: add PyInstaller dev dep + exe entry scripts"
```

---

### Task 2: Converter.exe spec + build + end-to-end validation

**Files:**
- Create: `build/converter.spec`

- [ ] **Step 1: Write `build/converter.spec`** (onefile, console; bundle MoodysInternalData)

```python
# -*- mode: python ; coding: utf-8 -*-
import os
project_dir = os.path.abspath(os.path.join(SPECPATH, ".."))

hiddenimports = [
    "pandas", "yaml", "openpyxl", "openpyxl.cell._writer",
    "pandas._libs.tslibs.timedeltas", "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.np_datetime",
]

datas = []
_moodys = os.path.join(project_dir, "MoodysInternalData")
if os.path.exists(_moodys):
    datas.append((_moodys, "MoodysInternalData"))

a = Analysis(
    [os.path.join(project_dir, "build", "converter_main.py")],
    pathex=[project_dir], binaries=[], datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name="Converter", debug=False, strip=False, upx=True,
          console=True, disable_windowed_traceback=False,
          runtime_tmpdir=None, target_arch=None, icon=None)
```

- [ ] **Step 2: Build** (from project root; PyInstaller writes to `dist/Converter.exe`)

Run: `.\.venv\Scripts\pyinstaller --clean --noconfirm --distpath dist --workpath build\_work build\converter.spec`
Expected: `dist\Converter.exe` created. If a module is missing at build/run, add it to `hiddenimports` and rebuild.

- [ ] **Step 3: End-to-end validation vs the golden oracle**

Run the frozen exe on the real local data and compare to the original tool's output:
```powershell
.\dist\Converter.exe configs\convert.local.yaml
.\.venv\Scripts\python scripts\compare_outputs.py "C:\Users\peic\AppData\Local\Temp\pit_validate\orig_out" output
```
Expected: `RESULT: EQUIVALENT` (exit 0). If the orig_out oracle is gone, regenerate it by running the old `RICSConverter.exe` on the same config (see `tests/golden_master/README.md`). The exe finds MoodysInternalData from its bundle (`_MEIPASS`), so `moodys_internal_data` in the config is not needed for the exe.

- [ ] **Step 4: Commit**

```bash
git add build/converter.spec
git commit -m "build: Converter.exe spec (bundles MoodysInternalData); validated vs golden output"
```

---

### Task 3: Importer.exe spec + build + smoke

**Files:**
- Create: `build/importer.spec`

- [ ] **Step 1: Write `build/importer.spec`** (onefile, console; pythonnet/clr hidden imports; no SG/data bundling)

```python
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all
project_dir = os.path.abspath(os.path.join(SPECPATH, ".."))

hiddenimports = [
    "pythonnet", "clr", "pandas", "yaml",
    "pandas._libs.tslibs.timedeltas", "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.np_datetime",
]
datas = []
binaries = []
# pythonnet ships runtime DLLs (Python.Runtime.dll, clr loader) — collect them.
try:
    _d, _b, _h = collect_all("pythonnet")
    datas += _d; binaries += _b; hiddenimports += _h
except Exception:
    pass
try:
    _d2, _b2, _h2 = collect_all("clr_loader")
    datas += _d2; binaries += _b2; hiddenimports += _h2
except Exception:
    pass

a = Analysis(
    [os.path.join(project_dir, "build", "importer_main.py")],
    pathex=[project_dir], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name="Importer", debug=False, strip=False, upx=True,
          console=True, disable_windowed_traceback=False,
          runtime_tmpdir=None, target_arch=None, icon=None)
```

- [ ] **Step 2: Build**

Run: `.\.venv\Scripts\pyinstaller --clean --noconfirm --distpath dist --workpath build\_work build\importer.spec`
Expected: `dist\Importer.exe` created.

- [ ] **Step 3: Smoke test (no SG needed)**

Run: `.\dist\Importer.exe --version`  → prints `Portfolio Import Tool Importer 0.1.0`, exit 0.
Run: `.\dist\Importer.exe --help`  → prints usage, exit 0.
(These do not load `clr`/SG — `sg_api.init_sg` is only called during an actual import, which is the user's live-SG step.)
If freezing pythonnet fails or the exe errors on `--version`, iterate: if onefile is problematic for pythonnet, switch this spec to onedir (add a `COLLECT(...)` and drop `a.binaries/a.datas` from `EXE`), and note it. `--version` must pass.

- [ ] **Step 4: Commit**

```bash
git add build/importer.spec
git commit -m "build: Importer.exe spec (pythonnet bundled); --version smoke passes"
```

---

### Task 4: `build_all.bat` + README build section

**Files:**
- Create: `build/build_all.bat`
- Modify: `README.md` (add a "Building the executables" section)

- [ ] **Step 1: `build/build_all.bat`**

```bat
@echo off
REM Build both executables into dist\ using the project venv.
setlocal
cd /d "%~dp0.."
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\converter.spec
if errorlevel 1 exit /b 1
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\importer.spec
if errorlevel 1 exit /b 1
echo Built dist\Converter.exe and dist\Importer.exe
```

- [ ] **Step 2: README** — add a "Building the executables" section: run `build\build_all.bat` (or the two pyinstaller commands); outputs land in `dist\`; the workbook's exe-path fields default to `.\dist\Converter.exe` / `.\dist\Importer.exe`; Converter bundles MoodysInternalData; Importer requires Moody's SG at runtime.

- [ ] **Step 3: Commit**

```bash
git add build/build_all.bat README.md
git commit -m "build: build_all.bat + README build instructions"
```

---

## Self-Review

- **Coverage (spec §8 Part 6):** two `.spec` files, `Converter.exe` (bundles MoodysInternalData) + `Importer.exe` (pythonnet), `build_all.bat`, docs. ✓
- **Validation:** Converter.exe proven via `compare_outputs.py` EQUIVALENT (strongest — end-to-end frozen run vs the original); Importer.exe `--version`/`--help` smoke (live SG import is the user's manual step). ✓
- **No placeholders:** full spec/entry/bat code given; commands exact.
- **Risks:** pythonnet onefile freezing can be finicky — Task 3 Step 3 has the onedir fallback. UPX may be absent (harmless; PyInstaller skips it) — if UPX errors, set `upx=False`. If the golden oracle `orig_out` is missing, Task 2 Step 3 says how to regenerate it.
- **Env:** build with `.venv` (pandas 2.x). `dist/`, `build/_work/` gitignored.
