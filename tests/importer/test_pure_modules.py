import os

from pit.importer.bho import BHOFileGenerator
from pit.importer.read_rics_files import merge_folders_to_base, read_rics_files


def test_bho_generate_string_is_valid_xml():
    gen = BHOFileGenerator("TotalReturn", ["IssuerA.Bond1", "IssuerB.Bond2"])
    xml = gen.generate_string()
    assert xml.strip().startswith("<output")
    assert "Bond1" in xml or "IssuerA" in xml  # bond ids embedded


def test_merge_folders_to_base_combines_and_returns_path(tmp_path):
    base = tmp_path / "granularCounterparty"
    (base / "GC").mkdir(parents=True)
    (base / "GCP_CLO").mkdir(parents=True)
    (base / "GC" / "1_GranularCounterparty.csv").write_text("Name,X\na,1\n", encoding="utf-8")
    (base / "GCP_CLO" / "1_GranularCounterparty.csv").write_text("Name,X\nb,2\n", encoding="utf-8")
    merged = merge_folders_to_base(str(base), "GC", ["GCP_CLO"])
    assert os.path.isdir(merged)
    assert "GC_Merged" in merged


def test_read_rics_files_classifies_subfolders(tmp_path):
    base = tmp_path / "granularCounterparty"
    (base / "GC").mkdir(parents=True)
    (base / "GC" / "1_GranularCounterparty.csv").write_text("Name\na\n", encoding="utf-8")
    rics_data, rics_info, csv_portfolio_files = read_rics_files(str(base))
    assert "GC" in rics_data
    assert isinstance(rics_data, dict)
    assert isinstance(rics_info, dict)
    assert isinstance(csv_portfolio_files, dict)
