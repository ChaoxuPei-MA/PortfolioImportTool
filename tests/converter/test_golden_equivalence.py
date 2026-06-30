"""Proves the migrated converter produces output equivalent to the original.

The reference ("golden") is the output tree of the working original converter
(e.g. the released RICSConverter.exe). Equivalence is numeric-tolerant, not
byte-exact: floating-point summation order differs by ~1e-16 across pandas/numpy
patch versions, so float columns are compared within a tolerance while every
non-float column and non-CSV file must match exactly. The timestamped summary
file is ignored.

Opt-in: runs only when PIT_GOLDEN=1 and the local golden tree + sample config
exist (neither is committed). Otherwise it skips so normal test runs stay green.

Setup (run once, locally, with pandas 2.x):
    $env:PIT_GOLDEN = "1"
    $env:PIT_GOLDEN_DIR = "C:\\scratch\\orig_out"            # original converter's output tree
    $env:PIT_CONVERT_SAMPLE_CONFIG = "C:\\scratch\\convert_config.yaml"  # output_path -> a fresh scratch dir
    python -m pytest tests/converter/test_golden_equivalence.py -v
"""
import os

import pytest

from pit.shared.config import load_config
from pit.converter import pipeline
from tests.golden_master.compare import compare_trees

# The summary file embeds a generation timestamp, so it is never byte-stable.
IGNORE_FILES = {"RICS_Format_Converter_Summary.txt"}
FLOAT_ATOL = 1e-9


def _golden_dir():
    return os.environ.get("PIT_GOLDEN_DIR", "")


def _sample_config():
    return os.environ.get("PIT_CONVERT_SAMPLE_CONFIG", "")


def _should_run():
    return (
        os.environ.get("PIT_GOLDEN") == "1"
        and os.path.isdir(_golden_dir())
        and os.path.exists(_sample_config())
    )


@pytest.mark.skipif(not _should_run(), reason="golden tree / sample config not configured")
def test_migrated_output_matches_golden():
    config = load_config(_sample_config())
    # The sample config's moodys_internal_data must be a real local path.
    summaries = pipeline.run(config)
    assert summaries is not None

    output_tree = config["converter_paths"]["output_path"]
    diffs = compare_trees(
        _golden_dir(), output_tree, float_atol=FLOAT_ATOL, ignore_files=IGNORE_FILES
    )
    assert diffs == [], (
        "Migrated converter output differs from the golden master:\n" + "\n".join(diffs)
    )
