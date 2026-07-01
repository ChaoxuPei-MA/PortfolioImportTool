import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import scripts.run_pipeline as rp


def test_reformat_date():
    assert rp.reformat_date("20250630") == "2025-06-30"
    assert rp.reformat_date("2025-06-30") == "2025-06-30"


def test_run_links_output_and_date_then_imports(monkeypatch):
    calls = {}
    monkeypatch.setattr(rp.converter_cli, "run_converter_with_config",
                        lambda cfg: (calls.__setitem__("convert", cfg), 0)[1])
    monkeypatch.setattr(rp.importer_cli, "run_import_with_config",
                        lambda cfg: (calls.__setitem__("import", cfg), 0)[1])
    combined = {
        "convert": {"start_date": "20251231", "converter_paths": {"output_path": "C:/out/rics"}},
        "import": {"paths": {}, "settings": {}},
    }
    rc = rp.run(combined)
    assert rc == 0
    assert calls["import"]["paths"]["rics_path"] == "C:/out/rics"     # auto-linked
    assert calls["import"]["settings"]["base_date"] == "2025-12-31"   # shared date


def test_import_skipped_when_convert_fails(monkeypatch):
    monkeypatch.setattr(rp.converter_cli, "run_converter_with_config", lambda cfg: 1)
    ran = {"import": False}
    monkeypatch.setattr(rp.importer_cli, "run_import_with_config",
                        lambda cfg: ran.__setitem__("import", True) or 0)
    rc = rp.run({"convert": {"start_date": "20250630", "converter_paths": {"output_path": "x"}},
                 "import": {"paths": {}, "settings": {}}})
    assert rc == 1 and ran["import"] is False
