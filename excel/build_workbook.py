"""Build excelTool\\Portfolio_Import_Tool.xlsm from excel\\PortfolioImportTool.bas.

Requires Excel + AccessVBOM=1. Run with the venv python:
    .\\.venv\\Scripts\\python excel\\build_workbook.py
"""
from __future__ import annotations
import os
import sys

import win32com.client as win32

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAS = os.path.join(ROOT, "excel", "PortfolioImportTool.bas")
OUT = os.path.join(ROOT, "excelTool", "Portfolio_Import_Tool.xlsm")
XLSM = 52


def build(bas_path: str = BAS, out_xlsm: str = OUT) -> str:
    os.makedirs(os.path.dirname(out_xlsm), exist_ok=True)
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Add()
        wb.VBProject.VBComponents.Import(bas_path)
        xl.Run("CreateConfigSheets")
        if os.path.exists(out_xlsm):
            os.remove(out_xlsm)
        wb.SaveAs(out_xlsm, FileFormat=XLSM)
        wb.Close(False)
        return out_xlsm
    finally:
        xl.Quit()


if __name__ == "__main__":
    print("Built:", build())
