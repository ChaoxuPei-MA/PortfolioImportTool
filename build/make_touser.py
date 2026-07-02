#!/usr/bin/env python
"""Assemble the self-contained ToUser/ distribution folder.

Copies the three built exes, the Excel workbook, the config templates, and the
UserGuide into ToUser/, and lays out the UserData/output structure. Zip ToUser/
and share — the recipient follows ToUser/UserGuide.md.

Run AFTER building the exes (build/build_all.bat) and the workbook:
    .\\.venv\\Scripts\\python build\\make_touser.py
"""
from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "touser")
OUT = os.path.join(ROOT, "ToUser")

EXES = ["Converter.exe", "Importer.exe", "Pipeline.exe"]
WORKBOOK = os.path.join(ROOT, "excelTool", "Portfolio_Import_Tool.xlsm")

USERDATA_DIRS = [
    "UserData/granularCounterparty/GC",
    "UserData/granularCounterparty/GCCRE",
    "UserData/granularCounterparty/AgencyMBS",
    "UserData/portfolio",
]

GRANULAR_README = (
    "Put your input CSVs here, named <Folder>_<Type>.csv. Example for GC:\n"
    "  GC_Issuers.csv, GC_IndustryFactors.csv, GC_Instruments.csv,\n"
    "  GC_LGDs.csv, GC_Cashflows.csv\n"
    "GCCRE uses GCCRE_*.csv (with GCCRE_GeographyPropertyFactors.csv);\n"
    "AgencyMBS uses AgencyMBS_Issuers.csv, AgencyMBS_Instruments.csv, AgencyMBS_Laggard.csv.\n"
    "See UserGuide.md for details.\n"
)
PORTFOLIO_README = "Put Portfolios.csv and Holdings.csv here. See UserGuide.md.\n"


def _copy(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  copied {os.path.relpath(dst, OUT)}")


def main() -> int:
    dist = os.path.join(ROOT, "dist")
    missing = [e for e in EXES if not os.path.exists(os.path.join(dist, e))]
    if missing:
        print(f"ERROR: missing exes in dist/: {missing}. Build them first "
              f"(build\\build_all.bat).", file=sys.stderr)
        return 1
    if not os.path.exists(WORKBOOK):
        print(f"ERROR: workbook not found: {WORKBOOK}. Build it first "
              f"(excel\\build_workbook.py).", file=sys.stderr)
        return 1

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    print(f"Assembling {OUT} ...")

    for e in EXES:
        _copy(os.path.join(dist, e), os.path.join(OUT, "dist", e))
    _copy(WORKBOOK, os.path.join(OUT, "Portfolio_Import_Tool.xlsm"))
    _copy(os.path.join(SRC, "UserGuide.md"), os.path.join(OUT, "UserGuide.md"))
    for name in os.listdir(os.path.join(SRC, "configs")):
        _copy(os.path.join(SRC, "configs", name), os.path.join(OUT, "configs", name))

    for d in USERDATA_DIRS:
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    for gd in ("GC", "GCCRE", "AgencyMBS"):
        with open(os.path.join(OUT, "UserData", "granularCounterparty", gd, "README.txt"),
                  "w", encoding="utf-8") as f:
            f.write(GRANULAR_README)
    with open(os.path.join(OUT, "UserData", "portfolio", "README.txt"), "w", encoding="utf-8") as f:
        f.write(PORTFOLIO_README)
    # RICSFormatData/ holds the Convert output (RICS bulk-import files) and the
    # Import .bhs. Pre-created so users see where results land.
    os.makedirs(os.path.join(OUT, "RICSFormatData"), exist_ok=True)
    with open(os.path.join(OUT, "RICSFormatData", "README.txt"), "w", encoding="utf-8") as f:
        f.write("Convert writes RICS bulk-import files here; Import writes the .bhs here.\n")

    print("Done. Zip the ToUser folder and share it; recipients follow UserGuide.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
