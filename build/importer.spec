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
