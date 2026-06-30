"""Importer CLI — compiled into Importer.exe. Mirrors the original excel_wrapper.py
contract but uses the shared config/logging/results modules. Requires Moody's SG
at runtime (via pipeline -> sg_api); fully decoupled from the converter.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Optional

from pit.version import __version__
from pit.shared.config import load_config, ConfigError
from pit.shared.logging_setup import setup_logging
from pit.shared.results import Result, write_results
from pit.importer import pipeline

RESULTS_FILENAME = "rics_import_results.json"
LOG_FILENAME = "rics_import.log"


def _script_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def convert_excel_config_to_internal(excel_config: dict) -> dict:
    config = {
        "paths": {
            "runtime_config": excel_config.get("runtime_config", ""),
            "assembly_path": excel_config.get("assembly_path", ""),
            "data_path": excel_config.get("data_path", ""),
            "model_path": excel_config.get("model_path", ""),
            "licence_path": excel_config.get("licence_path", ""),
            "rics_path": excel_config.get("rics_path", ""),
            "output_path": excel_config.get("output_path", ""),
            "load_sim_path": excel_config.get("load_sim_path", ""),
        },
        "multiple_gcp_types": excel_config.get("multiple_gcp_types", {}),
        "settings": {
            "load_sim": excel_config.get("load_sim", False),
            "keep_existing_portfolios": excel_config.get("keep_existing_portfolios", False),
            "import_economies": excel_config.get("import_economies", True),
            "import_transition_matrices": excel_config.get("import_transition_matrices", True),
            "import_mpr_models": excel_config.get("import_mpr_models", True),
            "import_zscore_models": excel_config.get("import_zscore_models", True),
            "base_date": excel_config.get("base_date", "2025-06-30"),
            "base_economy": excel_config.get("base_economy", "USD"),
        },
    }
    for key in ("structured_portfolios_parameters",
                "userDefined_combined_structured_nonstructured_portfolios",
                "Issuer_Bond_Output"):
        if key in excel_config:
            config[key] = excel_config[key]
    return config


def run_import_with_config(config: dict) -> int:
    out_dir = _script_dir()
    log_path = setup_logging(os.path.join(out_dir, LOG_FILENAME))
    logger = logging.getLogger(__name__)
    try:
        pipeline.run(config)
        output_path = config["paths"]["output_path"]
        result = Result.success("Import completed successfully",
                                 output_path=output_path, log_file=log_path)
        write_results(result, out_dir, RESULTS_FILENAME)
        return 0
    except Exception as exc:
        logger.error("IMPORT FAILED: %s\n%s", exc, traceback.format_exc())
        write_results(Result.error(str(exc), log_file=log_path), out_dir, RESULTS_FILENAME)
        return 1


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        arg = argv[0]
        if arg in ("--help", "-h"):
            print("Portfolio Import Tool - Importer\n\n"
                  "Usage:\n"
                  "  Importer.exe [config.yaml]   Use a YAML config file\n"
                  "  Importer.exe --json <json>   Use a JSON config (from Excel)\n"
                  "  Importer.exe --version       Show version")
            return 0
        if arg in ("--version", "-v"):
            print(f"Portfolio Import Tool Importer {__version__}")
            return 0
        if arg == "--json":
            if len(argv) < 2:
                print("Error: --json requires a JSON string argument", file=sys.stderr)
                return 1
            return run_import_with_config(convert_excel_config_to_internal(json.loads(argv[1])))
        config_path = arg
        if not os.path.exists(config_path):
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            return 1
        try:
            config = load_config(config_path)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return run_import_with_config(config)

    default_config = os.path.join(_script_dir(), "config.yaml")
    if not os.path.exists(default_config):
        print("Error: no config provided and config.yaml not found", file=sys.stderr)
        return 1
    return run_import_with_config(load_config(default_config))


if __name__ == "__main__":
    sys.exit(main())
