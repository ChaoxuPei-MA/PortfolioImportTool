import json
import os

from pit.importer import cli


def test_version_returns_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "Portfolio Import Tool Importer" in capsys.readouterr().out


def test_help_returns_zero():
    assert cli.main(["--help"]) == 0


def test_apply_sg_path_derives_four_paths(tmp_path):
    sg = tmp_path / "SG"
    (sg / "Data").mkdir(parents=True)   # Data exists -> data_path = <sg>\Data
    (sg / "Models").mkdir()
    config = {"paths": {"sg_path": str(sg)}}
    cli.apply_sg_path(config)
    p = config["paths"]
    assert p["assembly_path"] == str(sg)
    assert p["runtime_config"].endswith("MoodysAnalytics.SG.UI.runtimeconfig.json")
    assert p["model_path"] == os.path.join(str(sg), "Models")
    assert p["data_path"] == os.path.join(str(sg), "Data")


def test_apply_sg_path_data_falls_back_to_root_when_no_data_dir(tmp_path):
    sg = tmp_path / "SG"     # no Data\ subfolder
    sg.mkdir()
    config = {"paths": {"sg_path": str(sg)}}
    cli.apply_sg_path(config)
    assert config["paths"]["data_path"] == str(sg)   # falls back to SG root


def test_apply_sg_path_noop_without_sg_path():
    config = {"paths": {"assembly_path": "X"}}
    cli.apply_sg_path(config)
    assert "runtime_config" not in config["paths"]   # nothing derived


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
