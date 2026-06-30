"""Data-type -> processor dispatch for the converter.

Replaces the original main.py if/elif chain. A new granular type is added by
registering a handler — pipeline.run does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from pit.converter.processors.granular import GC_GCCRE_GCRETAIL
from pit.converter.processors.agency_mbs import AgencyMBS


@dataclass
class HandlerContext:
    start_date: str
    rics_version: str
    gcorr_data: dict
    params: dict
    rics_format: dict
    mapping_data: dict
    output_dir_granular: str


_REGISTRY: dict = {}


def _register(*data_types):
    def deco(fn):
        for dt in data_types:
            _REGISTRY[dt] = fn
        return fn
    return deco


def get_handler(data_type_upper: str) -> Optional[Callable]:
    return _REGISTRY.get(data_type_upper)


@_register("GC", "GCCRE", "GCRETAIL")
def _handle_granular(data_type_upper: str, data: dict, ctx: HandlerContext):
    proc = GC_GCCRE_GCRETAIL(
        data_type_upper, ctx.start_date, data, ctx.gcorr_data, ctx.params,
        ctx.rics_format, ctx.output_dir_granular, ctx.mapping_data, ctx.rics_version,
    )
    summary = proc.run()
    matured = summary.get("matured_instruments", []) if summary else []
    return data_type_upper.lower(), summary, matured


@_register("AGENCYMBS")
def _handle_agency_mbs(data_type_upper: str, data: dict, ctx: HandlerContext):
    proc = AgencyMBS("AgencyMBS", data, ctx.rics_format, ctx.output_dir_granular)
    summary = proc.run()
    removed = summary.get("removed_instruments", []) if summary else []
    return "agency_mbs", summary, removed
