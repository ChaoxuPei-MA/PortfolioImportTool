import json
import os

import pytest

from pit.converter import cli


def test_version_returns_zero(capsys):
    assert cli.main(["--version"]) == 0
    assert "Portfolio Import Tool Converter" in capsys.readouterr().out


def test_help_returns_zero():
    assert cli.main(["--help"]) == 0


def test_missing_config_file_returns_one(capsys):
    assert cli.main(["Z:/no/such/config.yaml"]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_excel_config_mapping_has_expected_shape():
    internal = cli.convert_excel_config_to_internal({
        "start_date": "20250630",
        "data_path": "C:/d", "output_path": "C:/o",
    })
    assert internal["start_date"] == "20250630"
    assert internal["converter_paths"]["data_path"] == "C:/d"
    assert internal["converter_paths"]["output_path"] == "C:/o"
    assert "file_types" in internal
    assert "GCorr_files" in internal


def test_resolve_moodys_data_finds_dir(tmp_path):
    d = tmp_path / "MoodysInternalData"
    d.mkdir()
    (d / "RICS_BulkImportFiles_Formats.csv").write_text("x\n", encoding="utf-8")
    config = {"moodys_internal_data": str(d)}
    assert os.path.normpath(cli.resolve_moodys_data(config)) == os.path.normpath(str(d))


def test_resolve_moodys_data_raises_when_absent(tmp_path):
    config = {"moodys_internal_data": str(tmp_path / "nope")}
    with pytest.raises(FileNotFoundError):
        cli.resolve_moodys_data(config)


def test_run_with_config_writes_results_and_returns_zero(tmp_path, monkeypatch):
    # Moody's data dir with the sentinel file so resolution passes.
    md = tmp_path / "MoodysInternalData"
    md.mkdir()
    (md / "RICS_BulkImportFiles_Formats.csv").write_text("x\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    config = {
        "moodys_internal_data": str(md),
        "converter_paths": {"output_path": str(out)},
    }
    # Stub the heavy pipeline; we are testing CLI wiring, not conversion.
    monkeypatch.setattr(cli.pipeline, "run", lambda cfg: {"ok": True})
    # Write results next to the cli module's dir — redirect to tmp by stubbing _script_dir.
    monkeypatch.setattr(cli, "_script_dir", lambda: str(out))
    rc = cli.run_converter_with_config(config)
    assert rc == 0
    results = json.load(open(os.path.join(str(out), "rics_converter_results.json")))
    assert results["status"] == "success"
