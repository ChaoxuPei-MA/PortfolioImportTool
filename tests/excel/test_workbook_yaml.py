"""Validate the VBA config-generation by driving Excel headlessly.

Builds a fresh workbook (imports the .bas, runs CreateConfigSheets), sets
known input cells via the row_<key> defined Names, then calls the
BuildConvertYAMLFromSheet / BuildImportYAMLFromSheet wrappers (collect+build
in one VBA call — avoids COM Dictionary marshalling issues), parses the YAML
with PyYAML, and asserts it matches the expected internal config structure.

Requires Excel + AccessVBOM=1. Skipped unless PIT_EXCEL=1 is set so the
default suite stays green on machines without Excel.

Architecture note: a single session-scoped Excel/workbook fixture is kept
alive for all tests to avoid COM apartment teardown crashes (0x80010108) that
occur when a second test tries to open Excel after the first test's finally
block called xl.Quit().
"""
from __future__ import annotations
import os
import pytest
import yaml

pytestmark = pytest.mark.skipif(
    os.environ.get("PIT_EXCEL") != "1",
    reason="set PIT_EXCEL=1 to run Excel-automation tests (needs Excel + AccessVBOM)",
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAS = os.path.join(ROOT, "excel", "PortfolioImportTool.bas")


@pytest.fixture(scope="session")
def xl_wb():
    """Session-scoped Excel + workbook fixture. One Excel process for all tests.

    xl.Quit() is intentionally NOT called in teardown — calling it during
    Python's COM apartment teardown triggers a fatal 0x80010108 crash. Excel
    closes on its own when the process exits (or via atexit / the OS reaper).
    """
    import win32com.client as win32
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    wb.VBProject.VBComponents.Import(BAS)
    xl.Run("CreateConfigSheets")
    yield xl, wb
    # Do not call xl.Quit() here — it causes a fatal COM crash (0x80010108)
    # during Python shutdown. Excel will be garbage-collected by the OS.


def _set(wb, sheet: str, key: str, value: str) -> None:
    """Set a named input cell via its row_<key> defined Name."""
    wb.Worksheets(sheet).Range("row_" + key).Value = value


# ---------------------------------------------------------------------------
# Convert YAML tests
# ---------------------------------------------------------------------------

def test_convert_yaml_matches_expected(xl_wb):
    """Convert tab: date derivation, paths, granular list, fixed keys."""
    xl, wb = xl_wb
    s = "PIT_Convert_Config"
    _set(wb, s, "data_path", "UserData")
    _set(wb, s, "output_path", "RICS_Files")
    _set(wb, s, "start_date", "06/30/2025")
    _set(wb, s, "granular", "GC, GCCRE, AgencyMBS")

    text = xl.Run("BuildConvertYAMLFromSheet", s)
    cfg = yaml.safe_load(text)

    # mm/dd/yyyy -> YYYYMMDD derivation
    assert cfg["start_date"] == "20250630", f"Expected '20250630', got {cfg['start_date']!r}"

    # paths preserved
    assert cfg["converter_paths"]["data_path"] == "UserData"
    assert cfg["converter_paths"]["output_path"] == "RICS_Files"

    # granular list parsed and stripped
    assert cfg["converter_data_types"]["granular"] == ["GC", "GCCRE", "AgencyMBS"]

    # fixed key present and correct
    assert cfg["moodys_internal_data"] == "MoodysInternalData"

    # parameters_default_values carries through
    assert cfg["parameters_default_values"]["CreditClass_default_value"] == "CS15"


# ---------------------------------------------------------------------------
# Import YAML tests
# ---------------------------------------------------------------------------

def test_import_yaml_derives_sg_paths_and_empty_outputs(xl_wb):
    """Import tab: SG Path derivations, base_economy, blank outputs => []."""
    xl, wb = xl_wb
    s = "PIT_Import_Config"
    sg = r"C:\Program Files\Moody's\SG\10.5.0"
    _set(wb, s, "sg_path", sg)
    _set(wb, s, "rics_path", "RICS_Files")
    _set(wb, s, "output_path", r"output\sim.bhs")
    _set(wb, s, "base_date", "2025-12-31")
    _set(wb, s, "base_economy", "CAD")
    # outputs/selection are now grids (empty by default) — no row_ cells to set.

    text = xl.Run("BuildImportYAMLFromSheet", s)
    cfg = yaml.safe_load(text)

    p = cfg["paths"]

    # assembly_path ends with SG version folder
    assert p["assembly_path"].endswith("10.5.0"), \
        f"assembly_path should end with '10.5.0', got {p['assembly_path']!r}"

    # runtime_config derived from SG path
    assert p["runtime_config"].endswith("MoodysAnalytics.SG.UI.runtimeconfig.json"), \
        f"runtime_config wrong: {p['runtime_config']!r}"

    # data_path and model_path sub-paths
    assert p["data_path"].endswith("/Data"), \
        f"data_path should end with '/Data', got {p['data_path']!r}"
    assert p["model_path"].endswith("/Models"), \
        f"model_path should end with '/Models', got {p['model_path']!r}"

    # settings value carried through
    assert cfg["settings"]["base_economy"] == "CAD"

    # blank inputs => no outputs (empty lists)
    ibo = cfg["Issuer_Bond_Output"]
    assert ibo["outputs"] == [], \
        f"Expected outputs=[], got {ibo['outputs']!r}"
    assert ibo["selection"] == [], \
        f"Expected selection=[], got {ibo['selection']!r}"


# ---------------------------------------------------------------------------
# Import YAML — grid default assertions
# ---------------------------------------------------------------------------

def test_import_yaml_gcp_default(xl_wb):
    """GC->GCP_CLO is the only prefilled row; others blank => only GC emitted."""
    xl, wb = xl_wb
    text = xl.Run("BuildImportYAMLFromSheet", "PIT_Import_Config")
    cfg = yaml.safe_load(text)
    assert cfg["multiple_gcp_types"] == {"GC": ["GCP_CLO"]}, \
        f"Expected {{'GC': ['GCP_CLO']}}, got {cfg['multiple_gcp_types']!r}"


def test_import_yaml_structured_defaults(xl_wb):
    """All 7 structured rows prefilled [False, 'USD', 'MarketValue']."""
    xl, wb = xl_wb
    text = xl.Run("BuildImportYAMLFromSheet", "PIT_Import_Config")
    cfg = yaml.safe_load(text)
    sp = cfg["structured_portfolios_parameters"]
    expected_keys = [
        "agency_cmbs", "structured_clo", "structured_cre", "structured_retail",
        "all_structured_selected", "all_structured", "all_structured_nonstructured",
    ]
    assert sorted(sp.keys()) == sorted(expected_keys), f"Keys mismatch: {list(sp.keys())!r}"
    for k, val in sp.items():
        assert val == [False, "USD", "MarketValue"], \
            f"{k}: expected [False, 'USD', 'MarketValue'], got {val!r}"


def test_import_yaml_userdefined_default_empty(xl_wb):
    """All 7 user-defined rows empty => {}."""
    xl, wb = xl_wb
    text = xl.Run("BuildImportYAMLFromSheet", "PIT_Import_Config")
    cfg = yaml.safe_load(text)
    ud = cfg["userDefined_combined_structured_nonstructured_portfolios"]
    assert ud == {}, f"Expected {{}}, got {ud!r}"


def test_import_yaml_output_default_empty(xl_wb):
    """All 8 output rows empty => outputs:[], selection:[] (no fallback)."""
    xl, wb = xl_wb
    text = xl.Run("BuildImportYAMLFromSheet", "PIT_Import_Config")
    cfg = yaml.safe_load(text)
    ibo = cfg["Issuer_Bond_Output"]
    assert ibo["outputs"] == [], f"Expected [], got {ibo['outputs']!r}"
    assert ibo["selection"] == [], f"Expected [], got {ibo['selection']!r}"


def test_import_yaml_output_row_set(xl_wb):
    """Set first output row => outputs=['CreditClass'], selection=[['All']]."""
    xl, wb = xl_wb
    s = "PIT_Import_Config"
    ws = wb.Worksheets(s)
    first_row = ws.Range("imp_out_first").Row
    ws.Cells(first_row, 1).Value = "CreditClass"
    ws.Cells(first_row, 2).Value = "All"
    try:
        text = xl.Run("BuildImportYAMLFromSheet", s)
        cfg = yaml.safe_load(text)
        ibo = cfg["Issuer_Bond_Output"]
        assert ibo["outputs"] == ["CreditClass"], f"outputs: {ibo['outputs']!r}"
        assert ibo["selection"] == [["All"]], f"selection: {ibo['selection']!r}"
    finally:
        # Restore defaults so other tests see an empty output grid.
        ws.Cells(first_row, 1).Value = ""
        ws.Cells(first_row, 2).Value = ""
