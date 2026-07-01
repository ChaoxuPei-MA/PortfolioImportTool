import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import scripts.run_import as ri


def test_delegates_to_importer_cli(monkeypatch):
    seen = {}
    monkeypatch.setattr(ri.importer_cli, "main", lambda argv: (seen.__setitem__("argv", argv), 0)[1])
    rc = ri.main(["some_import.yaml"])
    assert rc == 0 and seen["argv"] == ["some_import.yaml"]


def test_missing_arg_returns_2(capsys):
    assert ri.main([]) == 2
