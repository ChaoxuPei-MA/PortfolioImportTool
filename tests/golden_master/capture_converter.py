"""Capture a golden-master manifest of the ORIGINAL converter's output.

Usage (PowerShell), pointing at the existing original project + local converter config:

    $env:PIT_ORIG_CONVERTER  = "C:\\...\\Projects\\RICS_BulkImportFiles_Converter"
    $env:PIT_CONVERTER_CONFIG = "C:\\scratch\\convert\\config.yaml"
    python tests/golden_master/capture_converter.py C:\\scratch\\convert\\RICS_Files\\20250630

The script runs the original converter via its config, then writes
tests/golden/converter_manifest.json (gitignored) from the produced output tree.

This script is intentionally thin: it shells out to the original tool exactly as
the original Excel wrapper does, so the captured behavior is the real baseline.
"""
from __future__ import annotations

import os
import subprocess
import sys

from tests.golden_master.tree_hash import write_manifest

GOLDEN_DIR = os.path.join("tests", "golden")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: capture_converter.py <output_tree_dir>", file=sys.stderr)
        return 2
    output_tree = argv[1]

    orig = os.environ.get("PIT_ORIG_CONVERTER")
    if not orig:
        print("Set PIT_ORIG_CONVERTER to the original converter project dir.", file=sys.stderr)
        return 2

    config_path = os.environ.get("PIT_CONVERTER_CONFIG", os.path.join(orig, "config.yaml"))
    if not os.path.exists(config_path):
        print(f"Converter config not found: {config_path}", file=sys.stderr)
        return 2

    # Run the original converter in its own directory (matches wrapper behavior).
    env = dict(os.environ, RICS_CONFIG_PATH=config_path)
    print(f"Running original converter: {orig} with {config_path}")
    proc = subprocess.run(
        [sys.executable, "main.py"], cwd=orig, env=env,
        capture_output=True, text=True,
    )
    print(proc.stdout[-2000:])
    if proc.returncode != 0:
        print(proc.stderr[-4000:], file=sys.stderr)
        print("Original converter run FAILED — cannot capture baseline.", file=sys.stderr)
        return 1

    if not os.path.isdir(output_tree):
        print(f"Expected output tree not found: {output_tree}\n"
              f"Point this script at the converter's output_path/<start_date> folder.",
              file=sys.stderr)
        return 1

    os.makedirs(GOLDEN_DIR, exist_ok=True)
    manifest_path = os.path.join(GOLDEN_DIR, "converter_manifest.json")
    manifest = write_manifest(output_tree, manifest_path)
    print(f"Wrote {manifest_path} with {len(manifest)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
