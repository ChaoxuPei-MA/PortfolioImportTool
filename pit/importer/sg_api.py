"""The ONLY Moody's SG / .NET boundary.

pythonnet/CLR is imported lazily inside init_sg() so that importing this module
(and the rest of pit.importer) never requires a Moody's SG installation. Tests
bind a FakeSG instead of calling init_sg().
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class SG:
    sim: Any
    BulkImporter: Any
    ParameterSetImporter: Any
    DuplicateImportAction: Any
    String: Any
    File: Any


def init_sg(runtime_config: str, assembly_path: str, model_path: str,
            data_path: str, licence_path: str) -> SG:
    """Start the .NET CLR, load the SG API assembly, and build a licensed Simulation."""
    import pythonnet
    pythonnet.load("coreclr", runtime_config=runtime_config)
    if assembly_path not in sys.path:
        sys.path.append(assembly_path)
    import clr
    clr.AddReference("MoodysAnalytics.SG.API")
    from MoodysAnalytics.SG.API import (
        Simulation, BulkImporter, ParameterSetImporter, DuplicateImportAction,
    )
    from System import String
    from System.IO import File

    sim = Simulation()
    sim.InitialiseWithLicence(model_path, "", data_path, licence_path)
    return SG(
        sim=sim,
        BulkImporter=BulkImporter,
        ParameterSetImporter=ParameterSetImporter,
        DuplicateImportAction=DuplicateImportAction,
        String=String,
        File=File,
    )
