# -*- mode: python ; coding: utf-8 -*-
"""Pipeline.exe — convert THEN import from one combined config.
Bundles MoodysInternalData (for the convert stage) and pythonnet (for import).
"""
import os
from PyInstaller.utils.hooks import collect_all

project_dir = os.path.abspath(os.path.join(SPECPATH, ".."))

hiddenimports = [
    "run_pipeline",
    "pandas", "yaml", "openpyxl", "openpyxl.cell._writer",
    "pythonnet", "clr",
    "pandas._libs.tslibs.timedeltas", "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.np_datetime",
]

datas = []
_moodys = os.path.join(project_dir, "MoodysInternalData")
if os.path.exists(_moodys):
    datas.append((_moodys, "MoodysInternalData"))

binaries = []
for _pkg in ("pythonnet", "clr_loader"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

a = Analysis(
    [os.path.join(project_dir, "build", "pipeline_main.py")],
    pathex=[project_dir, os.path.join(project_dir, "scripts")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name="Pipeline", debug=False, strip=False, upx=True,
          console=True, disable_windowed_traceback=False,
          runtime_tmpdir=None, target_arch=None, icon=None)
