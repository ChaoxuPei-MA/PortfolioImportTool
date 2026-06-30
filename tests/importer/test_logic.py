# -*- coding: utf-8 -*-
"""
Characterization tests for pure logic functions in pit/importer/pipeline.py
and pit/importer/read_rics_files.py.

These tests LOCK the current (observed) behavior of the functions.
Do NOT modify these assertions to match aspirational behavior;
if production code changes, update these to reflect the new reality.
"""
import math
import pandas as pd
import pytest

from pit.importer.pipeline import (
    convert_to_param_value,
    sanitize_child_model_name,
    normalize_output_config,
)


# ---------------------------------------------------------------------------
# normalize_output_config
# ---------------------------------------------------------------------------

class TestNormalizeOutputConfig:
    """Lock behavior of normalize_output_config(config_dict) -> (outputs, selection)."""

    def test_empty_dict_returns_empty_pair(self):
        """No Issuer_Bond_Output key at all -> both lists empty."""
        outputs, selection = normalize_output_config({})
        assert outputs == []
        assert selection == []

    def test_missing_key_returns_empty_pair(self):
        """Unrelated top-level keys have no effect."""
        outputs, selection = normalize_output_config({"other_key": {}})
        assert outputs == []
        assert selection == []

    def test_blank_and_whitespace_outputs_are_stripped(self):
        """Blank and whitespace output names are filtered out."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": ["CreditClass", "  ", ""],
            "selection": [["GC"], ["  "], []],
        }}
        outputs, selection = normalize_output_config(cfg)
        # Only "CreditClass" survives on the outputs side
        assert "CreditClass" in outputs
        assert "" not in outputs
        assert "  " not in outputs

    def test_blank_outputs_reduce_pair_count_via_min_alignment(self):
        """After stripping blank outputs, pair count = min(len(outputs), len(selection))."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": ["CreditClass", "  ", ""],
            "selection": [["GC"], ["  "], []],
        }}
        outputs, selection = normalize_output_config(cfg)
        # outputs -> ["CreditClass"] (length 1)
        # selection -> [["GC"], [], []] (length 3, blanks inside sub-lists stripped)
        # pair_count = min(1, 3) = 1
        assert len(outputs) == 1
        assert len(selection) == 1
        assert outputs == ["CreditClass"]
        assert selection == [["GC"]]

    def test_normal_paired_config(self):
        """Normal two-output config is returned fully aligned."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": ["CreditClass", "TotalValue"],
            "selection": [["GC"], ["All"]],
        }}
        outputs, selection = normalize_output_config(cfg)
        assert outputs == ["CreditClass", "TotalValue"]
        assert selection == [["GC"], ["All"]]

    def test_more_outputs_than_selection_truncates_to_min(self):
        """Extra outputs with no paired selection are dropped."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": ["CreditClass", "TotalValue", "Recovery"],
            "selection": [["GC"], ["All"]],
        }}
        outputs, selection = normalize_output_config(cfg)
        assert len(outputs) == 2
        assert len(selection) == 2
        assert outputs == ["CreditClass", "TotalValue"]

    def test_outputs_as_scalar_string_is_wrapped_and_processed(self):
        """A scalar (non-list) outputs value is wrapped in a list before processing."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": "CreditClass",
            "selection": [["GC"]],
        }}
        outputs, selection = normalize_output_config(cfg)
        assert outputs == ["CreditClass"]
        assert selection == [["GC"]]

    def test_empty_selection_sublists_are_kept_as_empty_lists(self):
        """An empty sub-list [] in selection survives (no entries to strip)."""
        cfg = {"Issuer_Bond_Output": {
            "outputs": ["A", "B", "C"],
            "selection": [["x"], [], ["z"]],
        }}
        outputs, selection = normalize_output_config(cfg)
        # pair_count = min(3, 3) = 3; empty sub-list is kept
        assert outputs == ["A", "B", "C"]
        assert selection == [["x"], [], ["z"]]

    def test_output_and_selection_always_same_length(self):
        """The returned lists are always index-aligned (same length)."""
        for cfg in [
            {},
            {"Issuer_Bond_Output": {}},
            {"Issuer_Bond_Output": {"outputs": ["X", "Y"], "selection": [["a"]]}},
        ]:
            outputs, selection = normalize_output_config(cfg)
            assert len(outputs) == len(selection)


# ---------------------------------------------------------------------------
# convert_to_param_value
# ---------------------------------------------------------------------------

class TestConvertToParamValue:
    """Lock behavior of convert_to_param_value(value) -> str."""

    def test_float_integer_value_returns_int_string(self):
        """12.0 -> '12', not '12.0'."""
        assert convert_to_param_value(3.0) == "3"
        assert convert_to_param_value(12.0) == "12"
        assert convert_to_param_value(0.0) == "0"

    def test_int_value_returns_int_string(self):
        """Native Python int is stringified directly."""
        assert convert_to_param_value(3) == "3"
        assert convert_to_param_value(0) == "0"

    def test_non_integer_float_returns_float_string(self):
        """Non-integer floats are converted via str()."""
        assert convert_to_param_value(1.5) == "1.5"

    def test_nan_float_returns_nan_string(self):
        """float('nan') passes the pd.isna check and returns 'nan'."""
        result = convert_to_param_value(float("nan"))
        assert result == "nan"

    def test_pandas_na_returns_string_representation(self):
        """pd.NA triggers pd.isna -> returns str(pd.NA) which is '<NA>'."""
        result = convert_to_param_value(pd.NA)
        assert result == "<NA>"

    def test_string_passthrough(self):
        """Non-numeric strings are returned unchanged."""
        assert convert_to_param_value("ABC") == "ABC"
        assert convert_to_param_value("hello world") == "hello world"

    def test_numeric_string_integer_value(self):
        """'3.0' is parsed as numeric float-integer -> returns '3'."""
        assert convert_to_param_value("3.0") == "3"
        assert convert_to_param_value("3") == "3"


# ---------------------------------------------------------------------------
# sanitize_child_model_name
# ---------------------------------------------------------------------------

class TestSanitizeChildModelName:
    """Lock behavior of sanitize_child_model_name(model_name, child_type) -> str."""

    def test_slashes_and_spaces_replaced_with_underscores(self):
        """Special chars (/, space) are replaced by underscore."""
        result = sanitize_child_model_name("A/B", "Bond")
        assert "/" not in result
        assert result == "A_B"

    def test_hyphen_replaced_with_underscore(self):
        result = sanitize_child_model_name("test-name", "Bond")
        assert result == "test_name"

    def test_starts_with_digit_gets_child_type_prefix(self):
        """Name starting with a digit gets '{child_type}_' prepended."""
        result = sanitize_child_model_name("12 Bond/X", "Bond")
        assert result.startswith("Bond_")
        # After regex sub: '12 Bond/X' -> '12_Bond_X', then prepend 'Bond_'
        assert result == "Bond_12_Bond_X"

    def test_space_in_name_replaced(self):
        result = sanitize_child_model_name("Hello World", "Bond")
        assert " " not in result
        assert result == "Hello_World"

    def test_already_clean_name_unchanged(self):
        """Alphanumeric with underscore is left as-is."""
        assert sanitize_child_model_name("ABC_123", "Bond") == "ABC_123"

    def test_empty_string_returns_child_type(self):
        """Empty name falls back to child_type."""
        assert sanitize_child_model_name("", "Bond") == "Bond"

    def test_whitespace_only_returns_child_type(self):
        """Whitespace-only name: strip -> alnum sub -> empty -> child_type."""
        assert sanitize_child_model_name("  ", "Bond") == "Bond"

    def test_starts_with_letter_no_prefix_added(self):
        """Name starting with a letter does NOT get child_type prefix."""
        result = sanitize_child_model_name("ValidName", "Bond")
        assert result == "ValidName"
        assert not result.startswith("Bond_")


# ---------------------------------------------------------------------------
# generate_output_bho_files — "no values => no outputs" (user requirement lock)
# ---------------------------------------------------------------------------

class TestGenerateOutputBhoFiles:
    """
    Lock the user-required 'no values given => no outputs' behavior of
    generate_output_bho_files at the read_rics_files layer.
    """

    def test_empty_outputs_returns_empty_pair(self, tmp_path):
        """Empty Outputs list -> early return ([], []), no .bho files written."""
        from pit.importer.read_rics_files import generate_output_bho_files

        model_lists = {"output_data": {"GC": ["GC.IssuerA"]}}
        result = generate_output_bho_files(model_lists, [["All"]], [], str(tmp_path))
        assert result == ([], [])

    def test_empty_selection_returns_empty_pair(self, tmp_path):
        """Empty Selection list -> early return ([], []), no .bho files written."""
        from pit.importer.read_rics_files import generate_output_bho_files

        model_lists = {"output_data": {"GC": ["GC.IssuerA"]}}
        result = generate_output_bho_files(model_lists, [], ["CreditClass"], str(tmp_path))
        assert result == ([], [])

    def test_empty_outputs_writes_no_bho_files(self, tmp_path):
        """No .bho files are created when Outputs is empty."""
        from pit.importer.read_rics_files import generate_output_bho_files

        model_lists = {"output_data": {"GC": ["GC.IssuerA"]}}
        generate_output_bho_files(model_lists, [["All"]], [], str(tmp_path))
        bho_files = list(tmp_path.glob("*.bho"))
        assert bho_files == []

    def test_empty_selection_writes_no_bho_files(self, tmp_path):
        """No .bho files are created when Selection is empty."""
        from pit.importer.read_rics_files import generate_output_bho_files

        model_lists = {"output_data": {"GC": ["GC.IssuerA"]}}
        generate_output_bho_files(model_lists, [], ["CreditClass"], str(tmp_path))
        bho_files = list(tmp_path.glob("*.bho"))
        assert bho_files == []

    def test_both_empty_returns_empty_pair(self, tmp_path):
        """Both Outputs and Selection empty -> ([], []), no files."""
        from pit.importer.read_rics_files import generate_output_bho_files

        model_lists = {"output_data": {}}
        result = generate_output_bho_files(model_lists, [], [], str(tmp_path))
        assert result == ([], [])
        assert list(tmp_path.glob("*.bho")) == []
