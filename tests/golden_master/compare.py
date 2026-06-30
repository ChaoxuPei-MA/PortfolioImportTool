"""Numeric-tolerant comparison of two converter output trees.

Byte-hash equality (see tree_hash.py) is too strict for this pipeline:
floating-point summation order differs by ~1e-16 across pandas/numpy patch
versions, so two numerically-identical runs can produce different bytes in a
float column. This comparator reads CSVs and compares float columns within a
tolerance while requiring exact equality for every non-float column and every
non-CSV file. Known non-deterministic files (e.g. the timestamped summary) can
be ignored by name.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd


def _rel_files(root: str) -> dict:
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[rel] = full
    return out


def compare_trees(golden_dir: str, new_dir: str, float_atol: float = 1e-9,
                  ignore_files=()) -> list:
    """Return human-readable difference lines; empty list == equivalent.

    - CSV files: same columns and shape; float columns equal within ``float_atol``
      (absolute, NaN==NaN); all other columns exactly equal.
    - Non-CSV files: exact byte equality.
    - Files whose relative path is in ``ignore_files`` are skipped.
    """
    ignore = set(ignore_files)
    golden = _rel_files(golden_dir)
    new = _rel_files(new_dir)
    diffs: list[str] = []
    for rel in sorted(set(golden) | set(new)):
        if rel in ignore:
            continue
        if rel not in new:
            diffs.append(f"REMOVED: {rel}")
        elif rel not in golden:
            diffs.append(f"ADDED:   {rel}")
        else:
            diffs.extend(_compare_file(golden[rel], new[rel], rel, float_atol))
    return diffs


def _compare_file(a_path: str, b_path: str, rel: str, float_atol: float) -> list:
    if rel.lower().endswith(".csv"):
        return _compare_csv(a_path, b_path, rel, float_atol)
    with open(a_path, "rb") as fa, open(b_path, "rb") as fb:
        if fa.read() != fb.read():
            return [f"CHANGED (bytes): {rel}"]
    return []


def _compare_csv(a_path: str, b_path: str, rel: str, float_atol: float) -> list:
    a = pd.read_csv(a_path)
    b = pd.read_csv(b_path)
    if list(a.columns) != list(b.columns):
        return [f"CHANGED (columns): {rel}: {list(a.columns)} vs {list(b.columns)}"]
    if a.shape != b.shape:
        return [f"CHANGED (shape): {rel}: {a.shape} vs {b.shape}"]
    diffs = []
    for col in a.columns:
        a_float = pd.api.types.is_float_dtype(a[col])
        b_float = pd.api.types.is_float_dtype(b[col])
        if a_float and b_float:
            av, bv = a[col].to_numpy(), b[col].to_numpy()
            close = np.isclose(av, bv, atol=float_atol, rtol=0.0, equal_nan=True)
            if not close.all():
                maxd = float(np.nanmax(np.abs(av - bv)))
                diffs.append(
                    f"CHANGED (col '{col}', max abs diff {maxd:.2e} > atol {float_atol:.0e}): {rel}"
                )
        elif not a[col].equals(b[col]):
            diffs.append(f"CHANGED (col '{col}'): {rel}")
    return diffs
