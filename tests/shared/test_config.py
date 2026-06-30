import pytest

from pit.shared.config import ConfigError, load_config, require, get


def test_load_missing_file_raises_configerror():
    with pytest.raises(ConfigError) as exc:
        load_config("Z:/does/not/exist.yaml")
    assert "not found" in str(exc.value).lower()


def test_load_bad_yaml_raises_configerror(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("key: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(str(p))
    assert "yaml" in str(exc.value).lower()


def test_load_valid_yaml_returns_dict(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text("a: 1\nb:\n  c: hello\n", encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg == {"a": 1, "b": {"c": "hello"}}


def test_require_reports_all_missing_keys():
    cfg = {"converter_paths": {"output_path": "", "data_path": "C:/d"}}
    with pytest.raises(ConfigError) as exc:
        require(cfg, ["converter_paths.output_path", "start_date"])
    msg = str(exc.value)
    assert "converter_paths.output_path" in msg
    assert "start_date" in msg


def test_require_passes_when_all_present():
    cfg = {"start_date": "20250630", "converter_paths": {"output_path": "C:/o"}}
    require(cfg, ["start_date", "converter_paths.output_path"])  # no raise


def test_get_nested_with_default():
    cfg = {"a": {"b": 2}}
    assert get(cfg, "a.b") == 2
    assert get(cfg, "a.z", "fallback") == "fallback"
    assert get(cfg, "missing.path", None) is None
