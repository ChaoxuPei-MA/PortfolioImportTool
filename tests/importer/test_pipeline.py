# tests/importer/test_pipeline.py
import importlib

import pytest

from pit.importer import pipeline
from pit.shared.config import ConfigError


def test_import_has_no_side_effects():
    importlib.reload(pipeline)  # must not load CLR / construct Simulation
    assert pipeline.sim is None  # not bound until run()


def test_run_raises_configerror_on_missing_keys():
    with pytest.raises(ConfigError) as exc:
        pipeline.run({})
    msg = str(exc.value)
    assert "paths.runtime_config" in msg
    assert "settings.base_date" in msg


def test_run_invokes_init_sg_merge_and_main(tmp_path, monkeypatch):
    from pit.importer import pipeline
    from tests.importer.fakes import FakeSG

    calls = {"init_sg": 0, "merge": [], "main": 0}
    monkeypatch.setattr(pipeline.sg_api, "init_sg", lambda **kw: (calls.__setitem__("init_sg", calls["init_sg"] + 1) or FakeSG()))
    monkeypatch.setattr(pipeline, "merge_folders_to_base", lambda base, folder, types: calls["merge"].append((folder, tuple(types))))
    monkeypatch.setattr(pipeline, "main", lambda: calls.__setitem__("main", calls["main"] + 1))

    config = {
        "paths": {"runtime_config": "rc", "assembly_path": "ap", "data_path": "dp",
                   "model_path": "mp", "licence_path": "lp",
                   "rics_path": str(tmp_path), "output_path": str(tmp_path / "o.bhs"), "load_sim_path": ""},
        "multiple_gcp_types": {"GC": ["GCP_CLO"]},
        "structured_portfolios_parameters": {},
        "userDefined_combined_structured_nonstructured_portfolios": {},
        "settings": {"load_sim": False, "keep_existing_portfolios": False,
                      "import_economies": True, "import_transition_matrices": False,
                      "import_mpr_models": False, "import_zscore_models": False,
                      "base_date": "2025-12-31", "base_economy": "CAD"},
        "Issuer_Bond_Output": {},
    }
    pipeline.run(config)
    assert calls["init_sg"] == 1          # reached init_sg with correct Path_Infos keys (no KeyError)
    assert calls["merge"] == [("GC", ("GCP_CLO",))]  # merge pre-step ran
    assert calls["main"] == 1             # main ran after merge
