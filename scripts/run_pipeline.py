#!/usr/bin/env python
"""Run convert then import from one combined config.

Usage (project venv):  .\\.venv\\Scripts\\python scripts\\run_pipeline.py <config.yaml>

The config has two sections, `convert:` and `import:`. The convert stage's
output folder is auto-fed as the import stage's rics_path, and the convert
date is shared to import base_date. Import runs only if convert succeeds.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import yaml

from pit.converter import cli as converter_cli
from pit.importer import cli as importer_cli


def reformat_date(d: str) -> str:
    """YYYYMMDD -> YYYY-MM-DD; already-dashed input is returned unchanged."""
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def run(combined: dict) -> int:
    convert_cfg = combined["convert"]
    import_cfg = combined["import"]

    print("=== Stage 1/2: Convert ===")
    rc = converter_cli.run_converter_with_config(convert_cfg)
    if rc != 0:
        print(f"Convert failed (exit {rc}); skipping import.", file=sys.stderr)
        return rc

    # Auto-link: import reads the convert output; share the date.
    import_cfg.setdefault("paths", {})["rics_path"] = convert_cfg["converter_paths"]["output_path"]
    import_cfg.setdefault("settings", {})["base_date"] = reformat_date(convert_cfg["start_date"])

    print("=== Stage 2/2: Import ===")
    return importer_cli.run_import_with_config(import_cfg)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Usage: run_pipeline.py <combined_config.yaml>", file=sys.stderr)
        return 2
    path = argv[0]
    if not os.path.exists(path):
        print(f"Config not found: {path}", file=sys.stderr)
        return 2
    with open(path, "r", encoding="utf-8") as f:
        combined = yaml.safe_load(f)
    if not isinstance(combined, dict) or "convert" not in combined or "import" not in combined:
        print("Config must contain top-level 'convert:' and 'import:' sections.", file=sys.stderr)
        return 2
    return run(combined)


if __name__ == "__main__":
    raise SystemExit(main())
