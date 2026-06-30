import json
import os

from pit.importer import cli


def test_version_returns_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "Portfolio Import Tool Importer" in capsys.readouterr().out


def test_help_returns_zero():
    assert cli.main(["--help"]) == 0


def test_missing_config_returns_one(capsys):
    assert cli.main(["Z:/no/such/config.yaml"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_excel_config_mapping_shape():
    internal = cli.convert_excel_config_to_internal({
        "runtime_config": "rc", "assembly_path": "ap", "output_path": "out",
        "base_date": "2025-12-31", "base_economy": "CAD",
    })
    assert internal["paths"]["runtime_config"] == "rc"
    assert internal["paths"]["output_path"] == "out"
    assert internal["settings"]["base_economy"] == "CAD"


def test_run_with_config_writes_results(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    monkeypatch.setattr(cli.pipeline, "run", lambda cfg: None)
    monkeypatch.setattr(cli, "_script_dir", lambda: str(out))
    config = {"paths": {"output_path": str(out / "sim.bhs")}}
    rc = cli.run_import_with_config(config)
    assert rc == 0
    with open(os.path.join(str(out), "rics_import_results.json"), encoding="utf-8") as f:
        assert json.load(f)["status"] == "success"
