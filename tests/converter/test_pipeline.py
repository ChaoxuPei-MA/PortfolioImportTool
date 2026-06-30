import pytest

from pit.converter import pipeline
from pit.shared.config import ConfigError


def test_import_has_no_side_effects():
    # Importing pipeline must not read files or run anything.
    import importlib
    importlib.reload(pipeline)  # should not raise


def test_run_raises_configerror_on_missing_keys():
    with pytest.raises(ConfigError) as exc:
        pipeline.run({})
    msg = str(exc.value)
    assert "start_date" in msg
    assert "converter_paths.output_path" in msg
