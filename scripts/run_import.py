#!/usr/bin/env python
"""Run import only, from one standalone import config.

Usage (project venv):  .\\.venv\\Scripts\\python scripts\\run_import.py <import_config.yaml>

Thin wrapper over the importer CLI: the config points rics_path at already-
produced RICS format data (e.g. a prior convert run's output).
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pit.importer import cli as importer_cli


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Usage: run_import.py <import_config.yaml>", file=sys.stderr)
        return 2
    return importer_cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
