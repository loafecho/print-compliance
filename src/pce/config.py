"""Load the YAML config, deep-merging a user file over the bundled defaults."""
from __future__ import annotations

import copy
from importlib import resources
from pathlib import Path

import yaml


class ConfigError(ValueError):
    pass


def _defaults() -> dict:
    text = resources.files("pce").joinpath("default_config.yaml").read_text()
    return yaml.safe_load(text)


def _merge(base: dict, over: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k not in base:
            raise ConfigError(f"unknown config key: {path}{k}")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise ConfigError(f"config key {path}{k} must be a mapping")
            out[k] = _merge(base[k], v, f"{path}{k}.")
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None) -> dict:
    base = _defaults()
    if path is None:
        return base
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {p}")
    if p.suffix.lower() == ".toml":
        import tomllib

        user = tomllib.loads(p.read_text())
    else:
        user = yaml.safe_load(p.read_text()) or {}
    return _merge(base, user)
