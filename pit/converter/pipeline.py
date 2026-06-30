"""Converter orchestration. Refactored from the original main.py into a pure
run(config) -> summaries function with no import-time side effects.
"""
from __future__ import annotations

import os

import pandas as pd

from pit.shared.config import require
from pit.converter.processors.userdata import load_user_data, load_mapping_tables
from pit.converter.processors.convert_to_rics import (
    read_rics_import_format,
    apply_rics_version_format_filter,
)
from pit.converter.processors.registry import HandlerContext, get_handler
from pit.converter.processors.portfolio import Portfolio
from pit.converter.summary import write_summary_file

REQUIRED_KEYS = [
    "start_date",
    "GCorr_Corporate_version",
    "converter_paths.output_path",
    "moodys_internal_data",
]


def _load_gcorr_data(gcorr_info: dict, version: str) -> dict:
    data = {}
    if version == "2019":
        data["factors"] = pd.read_excel(gcorr_info["file_name"], sheet_name=gcorr_info["tabs"]["factors"])
        data["rsqs"] = pd.read_excel(gcorr_info["file_name"], sheet_name=gcorr_info["tabs"]["rsqs"])
    else:
        tmp = pd.read_csv(gcorr_info["file_name"]).rename(columns={"GCorrRsq": "RSQ"})
        data["factors"] = tmp.copy()
        data["rsqs"] = tmp[["pid", "RSQ"]].copy()
    return data


def _build_gcorr_info(config: dict, gcorr_corp_path: str, version: str) -> dict:
    base_filename = config["GCorr_files"]["file_name"].format(version=version)
    info: dict = {}
    if version == "2019":
        info["file_name"] = os.path.join(gcorr_corp_path, f"{base_filename}.xlsx")
        info["tabs"] = {
            "factors": config["GCorr_files"]["factors"].format(version=version),
            "rsqs": config["GCorr_files"]["rsqs"].format(version=version),
        }
    else:
        info["file_name"] = os.path.join(gcorr_corp_path, f"{base_filename}.csv")
        info["tabs"] = {}
    return info


def _process_portfolio(portfolio_data, all_matured, rics_import_format, output_dir):
    if not portfolio_data:
        print(f"Warning: Portfolio folder not found. Skipping portfolio processing.")
        return None
    key = "PORTFOLIO" if "PORTFOLIO" in portfolio_data else "portfolio"
    if key not in portfolio_data:
        print("Warning: Portfolio data not found (check configuration). Skipping.")
        return None
    files = portfolio_data[key]
    if not files or all(v is None for v in files.values()):
        print("Warning: No valid portfolio files found. Skipping.")
        return None

    if all_matured:
        print(f"\nFiltering {len(all_matured)} matured/removed instruments from holdings...")
        holdings_df = portfolio_data[key].get("Holdings")
        if holdings_df is not None and not holdings_df.empty:
            original_count = len(holdings_df)
            holdings_df["InstrumentID"] = (
                holdings_df["counterpartyName"].astype(str) + "."
                + holdings_df["instrumentName"].astype(str)
            )
            portfolio_data[key]["Holdings"] = (
                holdings_df[~holdings_df["InstrumentID"].isin(all_matured)]
                .drop(columns=["InstrumentID"]).reset_index(drop=True)
            )
            removed = original_count - len(portfolio_data[key]["Holdings"])
            print(f"  Removed {removed} matured/removed instrument holdings.")

    return Portfolio(portfolio_data[key], rics_import_format, output_dir).run()


def run(config: dict) -> dict:
    require(config, REQUIRED_KEYS)

    start_date = config["start_date"]
    gcorr_version = config["GCorr_Corporate_version"]
    rics_version = config.get("RICS_version", "10.6")

    data_path = config["converter_paths"].get("data_path", "")
    granular_path = os.path.join(data_path, "granularCounterparty")
    portfolio_path = os.path.join(data_path, "portfolio")
    output_dir = config["converter_paths"]["output_path"]

    granular_types = config["converter_data_types"]["granular"]
    portfolio_types = config["converter_data_types"]["portfolio"]
    granular_file_types = config["file_types"]["granular"]
    portfolio_file_types = config["file_types"]["portfolio"]

    moodys_data_path = config["moodys_internal_data"]
    gcorr_corp_path = os.path.join(
        moodys_data_path, config["GCorr_Corporate"].format(version=gcorr_version)
    )
    rics_format_file = os.path.join(moodys_data_path, "RICS_BulkImportFiles_Formats.csv")
    gcorr_info = _build_gcorr_info(config, gcorr_corp_path, gcorr_version)

    params = config["parameters_default_values"]
    mapping_file = config["Mapping_File"]
    mapping_tables = config["Mapping_Tables"]

    os.makedirs(output_dir, exist_ok=True)

    rics_import_format = read_rics_import_format(rics_format_file)
    rics_import_format = apply_rics_version_format_filter(rics_import_format, rics_version)
    mapping_data = load_mapping_tables(os.path.join(moodys_data_path, mapping_file), mapping_tables)
    gcorr_data = _load_gcorr_data(gcorr_info, gcorr_version)

    summaries: dict = {}
    all_matured: list = []

    data = load_user_data(granular_types, granular_file_types, granular_path)
    if granular_types:
        output_dir_granular = os.path.join(output_dir, "granularCounterparty")
        os.makedirs(output_dir_granular, exist_ok=True)
        ctx = HandlerContext(
            start_date=start_date, rics_version=rics_version, gcorr_data=gcorr_data,
            params=params, rics_format=rics_import_format, mapping_data=mapping_data,
            output_dir_granular=output_dir_granular,
        )
        for data_type in granular_types:
            dt = data_type.upper()
            if dt not in data:
                print(f"Warning: No data found for {data_type}. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            files = data[dt]
            if not files or all(v is None for v in files.values()):
                print(f"Warning: No valid files found for {data_type}. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            handler = get_handler(dt)
            if handler is None:
                print(f"Warning: Unknown data type '{data_type}'. Skipping {data_type} processing.")
                summaries[dt.lower()] = None
                continue
            summary_key, summary, matured = handler(dt, data[dt], ctx)
            summaries[summary_key] = summary
            all_matured.extend(matured)

    portfolio_data = load_user_data(portfolio_types, portfolio_file_types, portfolio_path)
    summaries["portfolio"] = _process_portfolio(
        portfolio_data, all_matured, rics_import_format, output_dir
    )

    write_summary_file(output_dir, start_date, summaries)
    print("RICS bulk import files generated successfully for date:", start_date)
    return summaries
