"""Converter CLI — the entry point compiled into Converter.exe.

Mirrors the original excel_wrapper.py contract (config file, or --json from
Excel) but uses the shared config/logging/results modules.
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
from pit.converter import pipeline

RESULTS_FILENAME = "rics_converter_results.json"
LOG_FILENAME = "rics_converter.log"
SUMMARY_FILENAME = "RICS_Format_Converter_Summary.txt"


def _script_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def convert_excel_config_to_internal(excel_config: dict) -> dict:
    return {
        "start_date": excel_config.get("start_date", "20250630"),
        "GCorr_Corporate_version": excel_config.get("GCorr_Corporate_version", "2019"),
        "RICS_version": excel_config.get("RICS_version", "10.6"),
        "converter_paths": {
            "data_path": excel_config.get("data_path", "./UserData"),
            "output_path": excel_config.get("output_path", "./RICS_Files"),
        },
        "converter_data_types": excel_config.get("converter_data_types", {
            "granular": ["GC", "GCCRE", "AgencyMBS"],
            "portfolio": ["portfolio"],
        }),
        "parameters_default_values": excel_config.get("parameters_default_values", {
            "ImpliedCreditClass_default_value": True,
            "CreditClass_default_value": "CS15",
            "interpolate_lgd_lgdk_for_amortising": False,
            "Using_GCorr_Corp_RSQ": False,
            "Using_GCorr_Corp_country": True,
            "Using_GCorr_Corp_industry": False,
            "corp_rsq_fill_default_value": True,
            "corp_rsq_default_value": 0.159719318,
            "corp_factors_fill_value_groupby": True,
            "corp_private_groupby_columnName": "securityType",
        }),
        "file_types": {
            "granular": ["issuers", "factors", "pds", "instruments", "lgd",
                         "cashflows", "couponPayments", "laggard"],
            "portfolio": ["Portfolios", "Holdings"],
        },
        "moodys_internal_data": excel_config.get("moodys_internal_data", "./MoodysInternalData/"),
        "GCorr_Corporate": "GCorr{version}",
        "GCorr_files": {
            "file_name": "GCorr {version} Corp R-Squared Factors",
            "factors": "GCorrCorpFactors{version}",
            "rsqs": "RatingRSQGCorr{version}",
        },
        "Mapping_File": "GCorr_MappingTables.xlsx",
        "Mapping_Tables": {
            "country": "CountryNameMapping",
            "countryRegion": "GCorrFactosMappping",
        },
        "model_assumptions": {"RSQ": {"GC": 0.159719318, "GCCRE": 0.2077}},
        "floating_reference_yield_curves": {"USD 0-EDF SPOT": "NominalYieldCurve"},
    }


def resolve_moodys_data(config: dict) -> str:
    relative = config.get("moodys_internal_data", "./MoodysInternalData/")
    script_dir = _script_dir()
    candidates = []
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", script_dir)
        candidates.append(os.path.join(bundle, "MoodysInternalData"))
    candidates += [
        relative,
        os.path.join(script_dir, "MoodysInternalData"),
        os.path.join(os.path.dirname(script_dir), "MoodysInternalData"),
        os.path.abspath("MoodysInternalData"),
    ]
    if not os.path.isabs(relative):
        candidates.append(os.path.abspath(os.path.join(script_dir, relative)))
        candidates.append(os.path.abspath(relative))
    for loc in candidates:
        loc = os.path.normpath(loc)
        if os.path.isdir(loc) and os.path.exists(os.path.join(loc, "RICS_BulkImportFiles_Formats.csv")):
            return os.path.abspath(loc)
    raise FileNotFoundError(
        "MoodysInternalData folder with RICS_BulkImportFiles_Formats.csv not found. Searched:\n"
        + "\n".join(f"  - {os.path.normpath(c)}" for c in candidates)
    )


def run_converter_with_config(config: dict) -> int:
    out_dir = _script_dir()
    log_path = setup_logging(os.path.join(out_dir, LOG_FILENAME))
    logger = logging.getLogger(__name__)
    try:
        config["moodys_internal_data"] = resolve_moodys_data(config)
        pipeline.run(config)
        output_path = config["converter_paths"]["output_path"]
        summary_file = os.path.join(output_path, SUMMARY_FILENAME)
        result = Result.success(
            "Conversion completed successfully",
            output_path=output_path,
            summary_file=summary_file if os.path.exists(summary_file) else None,
            log_file=log_path,
        )
        write_results(result, out_dir, RESULTS_FILENAME)
        return 0
    except Exception as exc:
        logger.error("CONVERSION FAILED: %s\n%s", exc, traceback.format_exc())
        write_results(Result.error(str(exc), log_file=log_path), out_dir, RESULTS_FILENAME)
        return 1


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        arg = argv[0]
        if arg in ("--help", "-h"):
            print("Portfolio Import Tool - Converter\n\n"
                  "Usage:\n"
                  "  Converter.exe [config.yaml]   Use a YAML config file\n"
                  "  Converter.exe --json <json>   Use a JSON config (from Excel)\n"
                  "  Converter.exe --version       Show version")
            return 0
        if arg in ("--version", "-v"):
            print(f"Portfolio Import Tool Converter {__version__}")
            return 0
        if arg == "--json":
            if len(argv) < 2:
                print("Error: --json requires a JSON string argument", file=sys.stderr)
                return 1
            config = convert_excel_config_to_internal(json.loads(argv[1]))
            return run_converter_with_config(config)
        config_path = arg
        if not os.path.exists(config_path):
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            return 1
        try:
            config = load_config(config_path)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return run_converter_with_config(config)

    if not os.path.exists("config.yaml"):
        print("Error: no config provided and config.yaml not found", file=sys.stderr)
        return 1
    return run_converter_with_config(load_config("config.yaml"))


if __name__ == "__main__":
    sys.exit(main())
