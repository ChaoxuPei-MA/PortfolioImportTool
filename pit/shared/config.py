"""YAML config loading and validation shared by both tools.

Raises ConfigError with actionable messages instead of leaking KeyError /
yaml internals to the user.
"""
from __future__ import annotations

import os
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when a config file is missing, malformed, or incomplete."""


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parsing error in {path}: {exc}") from exc
    if data is None:
        raise ConfigError(f"Config file is empty: {path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping, got {type(data).__name__}: {path}")
    return data


def get(config: dict, dotted_key: str, default: Any = None) -> Any:
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def require(config: dict, dotted_keys: list[str]) -> None:
    missing = []
    for key in dotted_keys:
        value = get(config, key, _MISSING)
        if value is _MISSING or value == "" or value is None:
            missing.append(key)
    if missing:
        raise ConfigError(
            "Missing or empty required config keys:\n"
            + "\n".join(f"  - {k}" for k in missing)
        )


_MISSING = object()
