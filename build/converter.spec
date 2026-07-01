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
