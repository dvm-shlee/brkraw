from __future__ import annotations

import os
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from .. import __version__

ENV_CONFIG_HOME = "BRKRAW_CONFIG_HOME"
DEFAULT_PROFILE_DIRNAME = ".brkraw"
DEFAULT_CONFIG_YAML = """# brkraw user configuration
# This file is optional. Delete it to fall back to package defaults.
# You can override the config root by setting BRKRAW_CONFIG_HOME.
brkraw_version: "{version}"
config_spec_version: 0
log_level: INFO
output_width: 120
# nifti_filename_template: "sub-<Subject.ID>_study-<Study.ID>_scan-<ScanID>_<Protocol>"
# Available tags: <Subject.ID>, <Study.ID>, <ScanID>, <Method>, <Protocol>
# Values come from `brkraw info` fields. Invalid filename characters are removed.
nifti_filename_template: "sub-<Subject.ID>_study-<Study.ID>_scan-<ScanID>_<Protocol>"
# float_decimals: 6
# rules_dir: rules
# specs_dir: specs
# transforms_dir: transforms
"""


@dataclass(frozen=True)
class ConfigPaths:
    root: Path
    config_file: Path
    specs_dir: Path
    rules_dir: Path
    transforms_dir: Path


def resolve_root(root: Optional[Union[str, Path]] = None) -> Path:
    if root is not None:
        return Path(root).expanduser()
    env_root = os.environ.get(ENV_CONFIG_HOME)
    if env_root:
        return Path(env_root).expanduser()
    return Path.home() / DEFAULT_PROFILE_DIRNAME


def get_paths(root: Optional[Union[str, Path]] = None) -> ConfigPaths:
    base = resolve_root(root)
    return ConfigPaths(
        root=base,
        config_file=base / "config.yaml",
        specs_dir=base / "specs",
        rules_dir=base / "rules",
        transforms_dir=base / "transforms",
    )


def paths(root: Optional[Union[str, Path]] = None) -> ConfigPaths:
    return get_paths(root=root)


def get_path(name: str, root: Optional[Union[str, Path]] = None) -> Path:
    paths_obj = get_paths(root=root)
    mapping = {
        "root": paths_obj.root,
        "config": paths_obj.config_file,
        "specs": paths_obj.specs_dir,
        "rules": paths_obj.rules_dir,
        "transforms": paths_obj.transforms_dir,
    }
    if name not in mapping:
        raise KeyError(f"Unknown config path: {name}")
    return mapping[name]


def is_initialized(root: Optional[Union[str, Path]] = None) -> bool:
    paths = get_paths(root)
    return paths.config_file.exists()


def ensure_initialized(
    root: Optional[Union[str, Path]] = None,
    *,
    create_config: bool = True,
    exist_ok: bool = True,
) -> ConfigPaths:
    paths = get_paths(root)
    if paths.root.exists() and not exist_ok:
        raise FileExistsError(paths.root)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.specs_dir.mkdir(parents=True, exist_ok=True)
    paths.rules_dir.mkdir(parents=True, exist_ok=True)
    paths.transforms_dir.mkdir(parents=True, exist_ok=True)
    if create_config and not paths.config_file.exists():
        paths.config_file.write_text(
            DEFAULT_CONFIG_YAML.format(version=__version__),
            encoding="utf-8",
        )
    return paths


def init(
    root: Optional[Union[str, Path]] = None,
    *,
    create_config: bool = True,
    exist_ok: bool = True,
) -> ConfigPaths:
    return ensure_initialized(root=root, create_config=create_config, exist_ok=exist_ok)


def load_config(root: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    paths = get_paths(root)
    if not paths.config_file.exists():
        return None
    with paths.config_file.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must contain a YAML mapping at the top level.")
    return data


def load(root: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    return load_config(root=root)


def clear_config(
    root: Optional[Union[str, Path]] = None,
    *,
    keep_config: bool = False,
    keep_rules: bool = False,
    keep_specs: bool = False,
    keep_transforms: bool = False,
) -> None:
    paths = get_paths(root=root)
    if not paths.root.exists():
        return
    if paths.config_file.exists() and not keep_config:
        paths.config_file.unlink()
    if paths.rules_dir.exists() and not keep_rules:
        _remove_tree(paths.rules_dir)
    if paths.specs_dir.exists() and not keep_specs:
        _remove_tree(paths.specs_dir)
    if paths.transforms_dir.exists() and not keep_transforms:
        _remove_tree(paths.transforms_dir)
    try:
        paths.root.rmdir()
    except OSError:
        pass


def clear(
    root: Optional[Union[str, Path]] = None,
    *,
    keep_config: bool = False,
    keep_rules: bool = False,
    keep_specs: bool = False,
    keep_transforms: bool = False,
) -> None:
    clear_config(
        root=root,
        keep_config=keep_config,
        keep_rules=keep_rules,
        keep_specs=keep_specs,
        keep_transforms=keep_transforms,
    )


def configure_logging(
    *,
    root: Optional[Union[str, Path]] = None,
    level: Optional[Union[str, int]] = None,
    stream=None,
) -> logging.Logger:
    config = load(root=root) or {}
    if level is None:
        level = config.get("log_level", "INFO")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    if not logging.getLogger().handlers:
        if level == logging.INFO:
            fmt = "%(message)s"
        else:
            fmt = "%(levelname)s %(asctime)s %(message)s"
        logging.basicConfig(level=level, format=fmt, stream=stream)
    return logging.getLogger("brkraw")


def output_width(root: Optional[Union[str, Path]] = None, default: int = 120) -> int:
    config = load(root=root) or {}
    width = config.get("output_width", default)
    try:
        return int(width)
    except (TypeError, ValueError):
        return default


def float_decimals(root: Optional[Union[str, Path]] = None, default: int = 6) -> int:
    config = load(root=root) or {}
    decimals = config.get("float_decimals", default)
    try:
        return int(decimals)
    except (TypeError, ValueError):
        return default


def affine_decimals(root: Optional[Union[str, Path]] = None, default: int = 6) -> int:
    return float_decimals(root=root, default=default)


def nifti_filename_template(
    root: Optional[Union[str, Path]] = None,
    default: str = "sub-<Subject.ID>_study-<Study.ID>_scan-<ScanID>_<Protocol>",
) -> str:
    config = load(root=root) or {}
    template = config.get("nifti_filename_template", default)
    return str(template)


def _remove_tree(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _remove_tree(child)
        else:
            child.unlink()
    path.rmdir()
