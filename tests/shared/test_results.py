import json
import os

from pit.shared.results import Result, write_results


def test_success_has_status_and_timestamp():
    r = Result.success("done", output_path="C:/out", summary_file="C:/out/summary.txt")
    d = r.to_dict()
    assert d["status"] == "success"
    assert d["message"] == "done"
    assert d["output_path"] == "C:/out"
    assert d["summary_file"] == "C:/out/summary.txt"
    assert d["timestamp"]  # non-empty ISO string


def test_error_omits_optional_paths():
    r = Result.error("boom", log_file="C:/x.log")
    d = r.to_dict()
    assert d["status"] == "error"
    assert d["message"] == "boom"
    assert d["log_file"] == "C:/x.log"
    assert d["output_path"] is None
    assert d["summary_file"] is None


def test_to_dict_key_order_is_fixed():
    r = Result.success("ok")
    assert list(r.to_dict().keys()) == [
        "status", "message", "timestamp", "output_path", "log_file", "summary_file",
    ]


def test_write_results_writes_named_file(tmp_path):
    r = Result.success("ok", output_path=str(tmp_path))
    path = write_results(r, str(tmp_path), "rics_converter_results.json")
    assert path == os.path.join(str(tmp_path), "rics_converter_results.json")
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["status"] == "success"


def test_write_results_never_raises_on_bad_dir():
    r = Result.error("x")
    # Non-existent nested dir that we don't create — must not raise.
    path = write_results(r, "Z:/no/such/dir/(probably)", "rics_import_results.json")
    assert path  # returns the intended path even if write failed
