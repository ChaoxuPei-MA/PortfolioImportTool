from pit.converter.processors.convert_to_rics import (
    rics_version_gte,
    apply_rics_version_format_filter,
)


def test_rics_version_gte_basic():
    assert rics_version_gte("10.6", "10.6") is True
    assert rics_version_gte("10.7", "10.6") is True
    assert rics_version_gte("11.0", "10.6") is True
    assert rics_version_gte("10.5", "10.6") is False
    assert rics_version_gte("10", "10.6") is False  # minor defaults to 0


def test_rics_version_gte_blank_or_none():
    assert rics_version_gte(None, "10.6") is False
    assert rics_version_gte("", "10.6") is False
    assert rics_version_gte("   ", "10.6") is False


def test_format_filter_drops_rbcfactors_below_106():
    fmt = {
        "ChildBond": ["Name", "RBCFactors", "Coupon"],
        "ChildFRN": ["Name", "RBCFactors"],
        "Other": ["RBCFactors"],  # not a child table -> untouched
    }
    out = apply_rics_version_format_filter(fmt, "10.5")
    assert out["ChildBond"] == ["Name", "Coupon"]
    assert out["ChildFRN"] == ["Name"]
    assert out["Other"] == ["RBCFactors"]


def test_format_filter_keeps_rbcfactors_at_106_and_is_a_copy():
    fmt = {"ChildBond": ["Name", "RBCFactors"]}
    out = apply_rics_version_format_filter(fmt, "10.6")
    assert out["ChildBond"] == ["Name", "RBCFactors"]
    # mutating the output must not change the input (defensive copy)
    out["ChildBond"].append("X")
    assert fmt["ChildBond"] == ["Name", "RBCFactors"]
