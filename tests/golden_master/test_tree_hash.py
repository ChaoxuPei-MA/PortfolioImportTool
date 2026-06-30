import json

from tests.golden_master.tree_hash import hash_tree, write_manifest, diff_manifests


def _make_tree(base):
    (base / "sub").mkdir()
    (base / "a.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (base / "sub" / "b.csv").write_text("p\n9\n", encoding="utf-8")


def test_hash_tree_is_deterministic_and_relative(tmp_path):
    _make_tree(tmp_path)
    h1 = hash_tree(str(tmp_path))
    h2 = hash_tree(str(tmp_path))
    assert h1 == h2
    assert set(h1.keys()) == {"a.csv", "sub/b.csv"}


def test_changed_file_changes_hash(tmp_path):
    _make_tree(tmp_path)
    before = hash_tree(str(tmp_path))
    (tmp_path / "a.csv").write_text("x,y\n1,3\n", encoding="utf-8")
    after = hash_tree(str(tmp_path))
    assert before["a.csv"] != after["a.csv"]
    assert before["sub/b.csv"] == after["sub/b.csv"]


def test_diff_manifests_reports_changes():
    a = {"f1": "h1", "f2": "h2", "f3": "h3"}
    b = {"f1": "h1", "f2": "CHANGED", "f4": "h4"}
    lines = diff_manifests(a, b)
    joined = "\n".join(lines)
    assert "f2" in joined          # changed
    assert "f3" in joined          # removed
    assert "f4" in joined          # added
    assert "f1" not in joined      # unchanged not reported


def test_write_manifest_roundtrip(tmp_path):
    _make_tree(tmp_path)
    out = tmp_path / "manifest.json"
    manifest = write_manifest(str(tmp_path), str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == manifest
