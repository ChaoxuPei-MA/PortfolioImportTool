"""Tests for the numeric-tolerant tree comparator."""
import pandas as pd

from tests.golden_master.compare import compare_trees


def _write_csv(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_float_within_tolerance_is_equivalent(tmp_path):
    g = tmp_path / "g"
    n = tmp_path / "n"
    _write_csv(g / "f.csv", pd.DataFrame({"Name": ["a", "b"], "Exposure": [0.5, 0.5]}))
    # differ by ~3e-16 in a float column -> must be treated as equivalent
    _write_csv(n / "f.csv", pd.DataFrame({"Name": ["a", "b"], "Exposure": [0.5 + 3e-16, 0.5]}))
    assert compare_trees(str(g), str(n), float_atol=1e-9) == []


def test_float_beyond_tolerance_is_flagged(tmp_path):
    g = tmp_path / "g"
    n = tmp_path / "n"
    _write_csv(g / "f.csv", pd.DataFrame({"Name": ["a"], "Exposure": [0.5]}))
    _write_csv(n / "f.csv", pd.DataFrame({"Name": ["a"], "Exposure": [0.5001]}))
    diffs = compare_trees(str(g), str(n), float_atol=1e-9)
    assert len(diffs) == 1 and "Exposure" in diffs[0]


def test_non_float_difference_is_flagged(tmp_path):
    g = tmp_path / "g"
    n = tmp_path / "n"
    _write_csv(g / "f.csv", pd.DataFrame({"Name": ["a"], "Code": ["X"]}))
    _write_csv(n / "f.csv", pd.DataFrame({"Name": ["a"], "Code": ["Y"]}))
    diffs = compare_trees(str(g), str(n))
    assert len(diffs) == 1 and "Code" in diffs[0]


def test_ignored_file_is_skipped(tmp_path):
    g = tmp_path / "g"
    n = tmp_path / "n"
    (g).mkdir(); (n).mkdir()
    (g / "summary.txt").write_text("generated 1\n", encoding="utf-8")
    (n / "summary.txt").write_text("generated 2\n", encoding="utf-8")
    assert compare_trees(str(g), str(n), ignore_files={"summary.txt"}) == []
    # without the ignore, it IS flagged
    assert compare_trees(str(g), str(n)) == ["CHANGED (bytes): summary.txt"]


def test_added_and_removed_files(tmp_path):
    g = tmp_path / "g"
    n = tmp_path / "n"
    (g).mkdir(); (n).mkdir()
    (g / "only_golden.csv").write_text("Name\na\n", encoding="utf-8")
    (n / "only_new.csv").write_text("Name\na\n", encoding="utf-8")
    diffs = compare_trees(str(g), str(n))
    assert "REMOVED: only_golden.csv" in diffs
    assert "ADDED:   only_new.csv" in diffs
