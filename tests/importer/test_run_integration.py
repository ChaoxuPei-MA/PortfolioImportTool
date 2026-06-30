# tests/importer/test_run_integration.py
"""
Mock-SG integration test: drives the full pipeline.run(config) flow with a
FakeSG injected at the SG boundary.  No live Moody's SG / .NET required.

Asserted call sequence
----------------------
sim.Create          -- new sim created (load_sim=False)
BulkImporter.Import or BulkImporter.ImportAsync -- at least one bulk import ran
sim.Save            -- simulation written to the configured output path
"""
import os

import pytest

from pit.importer import pipeline
from tests.importer.fakes import FakeSG
from tests.importer.make_rics_files import make_minimal_rics_tree


def test_run_with_fake_sg_drives_import_and_saves(tmp_path, monkeypatch):
    # ------------------------------------------------------------------
    # 1. Build the synthetic RICS file tree
    # ------------------------------------------------------------------
    rics = tmp_path / "RICS_Files"
    make_minimal_rics_tree(str(rics))
    out_bhs = tmp_path / "out.bhs"

    # ------------------------------------------------------------------
    # 2. Config mirrors what pipeline.run() parses (all required keys
    #    present; Issuer_Bond_Output={} means no BHO outputs generated
    #    so the flow skips BHO import and goes straight to sim.Save).
    # ------------------------------------------------------------------
    config = {
        "paths": {
            "runtime_config": "x",
            "assembly_path": "x",
            "data_path": "x",
            "model_path": "x",
            "licence_path": "x",
            "rics_path": str(rics),
            "output_path": str(out_bhs),
            "load_sim_path": "",
        },
        "multiple_gcp_types": {},
        "structured_portfolios_parameters": {},
        "userDefined_combined_structured_nonstructured_portfolios": {},
        "settings": {
            "load_sim": False,
            "keep_existing_portfolios": False,
            "import_economies": True,
            "import_transition_matrices": False,
            "import_mpr_models": False,
            "import_zscore_models": False,
            "base_date": "2025-12-31",
            "base_economy": "CAD",
        },
        "Issuer_Bond_Output": {},
    }

    # ------------------------------------------------------------------
    # 3. Inject FakeSG and suppress real sleeps (pipeline retries with
    #    time.sleep(1) per attempt; FakeBulkImporter registers models
    #    immediately so retries stop on attempt 1, but sleep(2) after
    #    import and sleep(1) in retry loop are still called).
    # ------------------------------------------------------------------
    fake = FakeSG()
    monkeypatch.setattr(pipeline.sg_api, "init_sg", lambda **kw: fake)
    monkeypatch.setattr("time.sleep", lambda _: None)

    # ------------------------------------------------------------------
    # 4. Run
    # ------------------------------------------------------------------
    pipeline.run(config)

    # ------------------------------------------------------------------
    # 5. Assert the SG call sequence
    # ------------------------------------------------------------------
    names = [c[0] for c in fake.calls]

    # New simulation was created (load_sim=False path)
    assert "sim.Create" in names, f"sim.Create not found in {names}"

    # At least one bulk import ran (GCP issuer import or portfolio import)
    bulk_import_calls = [n for n in names if n in ("BulkImporter.Import", "BulkImporter.ImportAsync")]
    assert bulk_import_calls, f"No BulkImporter.Import/ImportAsync found in {names}"

    # Simulation was saved
    assert "sim.Save" in names, f"sim.Save not found in {names}"

    # Save was called with the configured output path
    save_args = [c[1] for c in fake.calls if c[0] == "sim.Save"]
    assert save_args, "sim.Save call has no recorded args"
    assert any(str(out_bhs) in str(a[0]) for a in save_args), (
        f"sim.Save not called with output path {out_bhs}; got {save_args}"
    )
