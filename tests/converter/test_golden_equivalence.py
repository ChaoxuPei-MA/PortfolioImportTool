"""Proves the refactored converter produces output identical to the original.

Opt-in: runs only when PIT_GOLDEN=1 and the local baseline + sample config exist
(neither is committed). Otherwise it skips so normal test runs stay green.

Setup (run once, locally, after capturing the Plan-1 baseline):
    $env:PIT_GOLDEN = "1"
    $env:PIT_CONVERT_SAMPLE_CONFIG = "C:\\scratch\\convert\\config.yaml"  # output_path -> a scratch dir
    python -m pytest tests/converter/test_golden_equivalence.py -v
"""
import json
import os

import pytest

from pit.shared.config import load_config
from pit.converter import pipeline
from tests.golden_master.tree_hash import hash_tree, diff_manifests

GOLDEN_MANIFEST = os.path.join("tests", "golden", "converter_manifest.json")


def _should_run():
    return (
        os.environ.get("PIT_GOLDEN") == "1"
        and os.path.exists(GOLDEN_MANIFEST)
        and os.environ.get("PIT_CONVERT_SAMPLE_CONFIG")
        and os.path.exists(os.environ.get("PIT_CONVERT_SAMPLE_CONFIG", ""))
    )


@pytest.mark.skipif(not _should_run(), reason="golden baseline / sample config not configured")
def test_refactored_output_matches_golden():
    config = load_config(os.environ["PIT_CONVERT_SAMPLE_CONFIG"])
    # The sample config's moodys_internal_data must be a real local path.
    summaries = pipeline.run(config)
    assert summaries is not None

    output_tree = config["converter_paths"]["output_path"]
    new_manifest = hash_tree(output_tree)
    golden = json.load(open(GOLDEN_MANIFEST, encoding="utf-8"))

    diffs = diff_manifests(golden, new_manifest)
    assert diffs == [], "Refactored converter output differs from golden master:\n" + "\n".join(diffs)
