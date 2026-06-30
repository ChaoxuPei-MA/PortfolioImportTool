#!/usr/bin/env python
"""Compare two converter output trees (e.g. ours vs the original tool).

Equivalence is numeric-tolerant: exact for every integer/string value and every
non-CSV file, and within a floating-point tolerance for float columns (last-bit
summation noise differs ~1e-16 across pandas/numpy patch versions). The
timestamped summary file is ignored by default.

Usage (from the project root, with the venv python):
    .\\.venv\\Scripts\\python scripts\\compare_outputs.py <ORIGINAL_DIR> <NEW_DIR>
    .\\.venv\\Scripts\\python scripts\\compare_outputs.py A B --atol 1e-9
    .\\.venv\\Scripts\\python scripts\\compare_outputs.py A B --include-summary

Exit code: 0 if equivalent (within tolerance), 1 if there are real differences.

Example — compare a fresh run against the original RICSConverter.exe output:
    # 1) produce the original output once (self-contained exe, no Python needed):
    #    & "...\\RICS_BulkImportFiles_Converter\\dist\\RICSConverter.exe" "...\\orig_config.yaml"
    # 2) produce ours:
    #    .\\.venv\\Scripts\\python -m pit.converter.cli configs\\convert.local.yaml
    # 3) compare:
    #    .\\.venv\\Scripts\\python scripts\\compare_outputs.py "...\\orig_out" output
"""
from __future__ import annotations

import argparse
import os
import sys

# Make the project importable when run as a standalone script.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd

from tests.golden_master.compare import compare_trees
from tests.golden_master.tree_hash import hash_tree, diff_manifests

DEFAULT_IGNORE = {"RICS_Format_Converter_Summary.txt"}


def _float_delta_report(orig_dir: str, new_dir: str, rel_path: str) -> str:
    """For a CSV that differs at the byte level, quantify the float deltas."""
    try:
        a = pd.read_csv(os.path.join(orig_dir, rel_path))
        b = pd.read_csv(os.path.join(new_dir, rel_path))
    except Exception as exc:  # not a readable CSV pair
        return f"      (could not parse as CSV: {exc})"
    if a.shape != b.shape:
        return f"      shape differs: {a.shape} vs {b.shape}"
    float_cols = [c for c in a.columns if a[c].dtype.kind == "f" and c in b.columns]
    nonfloat_ok = all(a[c].equals(b[c]) for c in a.columns if c not in float_cols)
    max_delta = 0.0
    for c in float_cols:
        d = (a[c] - b[c]).abs().max()
        if pd.notna(d):
            max_delta = max(max_delta, float(d))
    return (f"      rows={len(a)}  non-float cols identical={nonfloat_ok}  "
            f"max float diff={max_delta:.2e}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compare two converter output trees (numeric-tolerant).")
    parser.add_argument("original_dir", help="reference output tree (e.g. the original tool's output)")
    parser.add_argument("new_dir", help="output tree to validate (e.g. ./output)")
    parser.add_argument("--atol", type=float, default=1e-9, help="float absolute tolerance (default 1e-9)")
    parser.add_argument("--include-summary", action="store_true",
                        help="also compare RICS_Format_Converter_Summary.txt (differs by timestamp)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.original_dir):
        print(f"ERROR: original_dir not found: {args.original_dir}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.new_dir):
        print(f"ERROR: new_dir not found: {args.new_dir}", file=sys.stderr)
        return 2

    ignore = set() if args.include_summary else set(DEFAULT_IGNORE)

    print(f"Original : {args.original_dir}")
    print(f"New      : {args.new_dir}")
    print(f"Tolerance: atol={args.atol:g}   ignoring={sorted(ignore) or 'nothing'}")
    print("-" * 70)

    # 1) The verdict: numeric-tolerant comparison.
    diffs = compare_trees(args.original_dir, args.new_dir, float_atol=args.atol, ignore_files=ignore)

    # 2) Transparency: raw byte-level diffs (always includes the summary), with
    #    float-delta detail for any differing CSV.
    byte_diffs = diff_manifests(hash_tree(args.original_dir), hash_tree(args.new_dir))
    if byte_diffs:
        print(f"Byte-level differences ({len(byte_diffs)}):")
        for line in byte_diffs:
            print(f"  {line}")
            if line.startswith("CHANGED: ") and line.endswith(".csv"):
                rel = line[len("CHANGED: "):]
                print(_float_delta_report(args.original_dir, args.new_dir, rel))
    else:
        print("Byte-level: identical (including summary).")

    print("-" * 70)
    if not diffs:
        print("RESULT: EQUIVALENT  (exact for all non-float data; floats within tolerance)")
        return 0
    print(f"RESULT: {len(diffs)} REAL DIFFERENCE(S) beyond tolerance:")
    for d in diffs:
        print(f"  {d}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
