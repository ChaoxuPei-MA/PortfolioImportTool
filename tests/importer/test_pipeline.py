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
