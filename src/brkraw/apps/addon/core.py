"""Addon installer utilities for specs and rules.

Last updated: 2025-12-30
"""

from __future__ import annotations

import importlib.resources as resources
import logging
import os
from pathlib import Path
from typing import Any, List, Dict, Tuple, Set, Optional, Union

import yaml

from ...core import config as config_core
from ...core import remapper
from ...core.rules import validator as rules_validator

logger = logging.getLogger("brkraw")

RULE_KEYS = {"info_spec", "metadata_spec", "converter_entrypoint"}


def add(path: Union[str, Path], root: Optional[Union[str, Path]] = None) -> List[Path]:
    """Install a spec or rule YAML file.

    Args:
        path: Source YAML file to install.
        root: Optional config root override.

    Returns:
        List of installed file paths.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    if src.suffix.lower() in {".yaml", ".yml"}:
        return _add_from_yaml(src, root=root)
    raise ValueError(f"Unsupported file type: {src}")


def add_spec_data(
    spec_data: Dict[str, Any],
    *,
    filename: Optional[str] = None,
    source_path: Optional[Path] = None,
    root: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """Install a spec from parsed data.

    Args:
        spec_data: Parsed spec mapping.
        filename: Target filename for the spec.
        source_path: Original spec file path (used for relative transforms).
        root: Optional config root override.

    Returns:
        List of installed file paths.
    """
    if not isinstance(spec_data, dict):
        raise ValueError("Spec data must be a mapping.")
    if filename is None:
        if source_path is None:
            raise ValueError("filename is required when source_path is not provided.")
        filename = source_path.name
    if not filename.endswith((".yaml", ".yml")):
        raise ValueError(f"Spec filename must be .yaml/.yml: {filename}")
    paths = config_core.paths(root=root)
    target = paths.specs_dir / filename
    installed = [target]
    installed_transforms, updated = _install_transforms_from_spec(
        spec_data,
        base_dir=source_path.parent if source_path else None,
        target_spec=target,
        root=root,
    )
    installed += installed_transforms
    content = yaml.safe_dump(spec_data, sort_keys=False)
    _write_file(target, content)
    logger.info("Installed spec: %s", target)
    return installed


def add_rule_data(
    rule_data: Dict[str, Any],
    *,
    filename: Optional[str] = None,
    source_path: Optional[Path] = None,
    root: Optional[Union[str, Path]] = None,
) -> List[Path]:
    """Install a rule file from parsed data.

    Args:
        rule_data: Parsed rule mapping.
        filename: Target filename for the rule file.
        source_path: Original rule file path (used for validation).
        root: Optional config root override.

    Returns:
        List of installed file paths.
    """
    if not isinstance(rule_data, dict):
        raise ValueError("Rule data must be a mapping.")
    if filename is None:
        if source_path is None:
            raise ValueError("filename is required when source_path is not provided.")
        filename = source_path.name
    if not filename.endswith((".yaml", ".yml")):
        raise ValueError(f"Rule filename must be .yaml/.yml: {filename}")
    rules_validator.validate_rules(rule_data)
    _ensure_rule_specs_present(rule_data, root=root)
    paths = config_core.paths(root=root)
    target = paths.rules_dir / filename
    content = yaml.safe_dump(rule_data, sort_keys=False)
    _write_file(target, content)
    logger.info("Installed rule: %s", target)
    return [target]


def install_examples(root: Optional[Union[str, Path]] = None) -> List[Path]:
    """Install bundled example specs and rules.

    Args:
        root: Optional config root override.

    Returns:
        List of installed file paths.
    """
    installed: List[Path] = []

    base = resources.files("brkraw.assets.examples")
    for rel_dir in ("specs", "rules"):
        src_dir = base / rel_dir
        if not src_dir.is_dir():
            continue
        for entry in src_dir.iterdir():
            name = entry.name
            if not (name.endswith(".yaml") or name.endswith(".yml")):
                continue
            content = entry.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                continue
            entry_path = Path(str(entry))
            if rel_dir == "specs":
                installed += add_spec_data(
                    data,
                    filename=name,
                    source_path=entry_path,
                    root=root,
                )
            else:
                installed += add_rule_data(
                    data,
                    filename=name,
                    source_path=entry_path,
                    root=root,
                )
    return installed

def list_installed(root: Optional[Union[str, Path]] = None) -> Dict[str, List[Dict[str, str]]]:
    """List installed specs and rules with metadata.

    Args:
        root: Optional config root override.

    Returns:
        Mapping with "specs" and "rules" lists for display.
    """
    paths = config_core.paths(root=root)
    result: Dict[str, List[Dict[str, str]]] = {"specs": [], "rules": [], "transforms": []}

    rule_entries = _load_rule_entries(paths.rules_dir)
    spec_categories = _spec_categories_from_rules(rule_entries)

    transforms_map: Dict[str, Set[str]] = {}
    if paths.specs_dir.exists():
        spec_files = list(paths.specs_dir.glob("*.yml")) + list(paths.specs_dir.glob("*.yaml"))
        for spec in sorted(spec_files):
            meta = _load_spec_meta(spec)
            name = meta.get("name")
            desc = meta.get("description")
            category = spec_categories.get(spec.name)
            result["specs"].append(
                {
                    "file": spec.name,
                    "name": name if name else "<Unknown>",
                    "description": desc if desc else "<Unknown>",
                    "category": category if category else "<Unknown>",
                    "name_unknown": "1" if not name else "0",
                    "description_unknown": "1" if not desc else "0",
                    "category_unknown": "1" if not category else "0",
                }
            )
            spec_label = spec.name
            for src in _collect_transforms_sources(spec):
                transforms_map.setdefault(Path(src).name, set()).add(spec_label)

    for entry in rule_entries:
        result["rules"].append(entry)

    for path in sorted(paths.transforms_dir.glob("*.py")):
        mapped = transforms_map.get(path.name)
        result["transforms"].append(
            {
                "file": path.name,
                "spec": ", ".join(sorted(mapped)) if mapped else "<Unknown>",
                "spec_unknown": "1" if not mapped else "0",
            }
        )

    return result


def remove(
    filename: Union[str, Path],
    *,
    root: Optional[Union[str, Path]] = None,
    kind: Optional[str] = None,
    force: bool = False,
) -> List[Path]:
    """Remove an installed spec or rule file by name.

    Args:
        filename: Filename of the spec/rule to remove.
        root: Optional config root override.
        kind: Optional target kind ("spec" or "rule").

    Returns:
        List of removed file paths.
    """
    name = Path(filename).name
    paths = config_core.paths(root=root)
    removed: List[Path] = []
    kinds = [kind] if kind else ["spec", "rule", "transform"]
    targets = _resolve_targets(name, kinds, paths)
    if not targets:
        raise FileNotFoundError(name)
    has_deps = False
    for target, item in targets:
        has_deps = _warn_dependencies(target, kind=item, root=root) or has_deps
    if has_deps and not force:
        raise RuntimeError("Dependencies found; use --force to remove.")
    for target, _ in targets:
        target.unlink()
        removed.append(target)
    if not removed:
        raise FileNotFoundError(name)
    return removed


def _warn_dependencies(target: Path, *, kind: str, root: Optional[Union[str, Path]]) -> bool:
    paths = config_core.paths(root=root)
    warned = False
    if kind == "spec":
        used_by_rules = _rules_using_spec(target.name, paths.rules_dir)
        if used_by_rules:
            logger.warning(
                "Spec %s is referenced by rules: %s",
                target.name,
                ", ".join(sorted(used_by_rules)),
            )
            warned = True
        included_by = _specs_including_spec(target.name, paths.specs_dir)
        if included_by:
            logger.warning(
                "Spec %s is included by: %s",
                target.name,
                ", ".join(sorted(included_by)),
            )
            warned = True
    elif kind == "transform":
        used_by_specs = _specs_using_transform(target.name, paths.specs_dir)
        if used_by_specs:
            logger.warning(
                "Transform %s is referenced by specs: %s",
                target.name,
                ", ".join(sorted(used_by_specs)),
            )
            warned = True
    return warned


def _resolve_targets(
    name: str,
    kinds: List[str],
    paths: config_core.ConfigPaths,
) -> List[Tuple[Path, str]]:
    targets: List[Tuple[Path, str]] = []
    for item in kinds:
        if item == "spec":
            base = paths.specs_dir
        elif item == "rule":
            base = paths.rules_dir
        elif item == "transform":
            base = paths.transforms_dir
        else:
            raise ValueError("kind must be 'spec' or 'rule' or 'transform'.")
        if not base.exists():
            continue
        matches = [path for path in base.glob(name) if path.is_file()]
        for path in matches:
            targets.append((path, item))
    return targets


def _rules_using_spec(spec_name: str, rules_dir: Path) -> Set[str]:
    used_by: Set[str] = set()
    if not rules_dir.exists():
        return used_by
    files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for key in RULE_KEYS:
            if key == "converter_entrypoint":
                continue
            for item in data.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                use = item.get("use")
                if isinstance(use, str) and Path(use).name == spec_name:
                    used_by.add(path.name)
    return used_by


def _specs_including_spec(spec_name: str, specs_dir: Path) -> Set[str]:
    included_by: Set[str] = set()
    if not specs_dir.exists():
        return included_by
    files = list(specs_dir.glob("*.yaml")) + list(specs_dir.glob("*.yml"))
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        meta = data.get("__meta__")
        include_list: List[str] = []
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
        if any(Path(item).name == spec_name for item in include_list):
            included_by.add(path.name)
    return included_by


def _specs_using_transform(transform_name: str, specs_dir: Path) -> Set[str]:
    used_by: Set[str] = set()
    if not specs_dir.exists():
        return used_by
    files = list(specs_dir.glob("*.yaml")) + list(specs_dir.glob("*.yml"))
    for path in files:
        for src in _collect_transforms_sources(path):
            if Path(src).name == transform_name:
                used_by.add(path.name)
                break
    return used_by


def _add_from_yaml(path: Path, root: Optional[Union[str, Path]]) -> List[Path]:
    """Install a spec or rule YAML after classifying the content.

    Args:
        path: YAML file path.
        root: Optional config root override.

    Returns:
        List of installed file paths.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"Empty YAML file: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"Rule/spec YAML must be a mapping: {path}")

    kind = _classify_yaml(data)
    if kind == "rule":
        return add_rule_data(data, filename=path.name, source_path=path, root=root)
    if kind == "spec":
        return add_spec_data(data, filename=path.name, source_path=path, root=root)
    raise ValueError(f"Unrecognized YAML file: {path}")


def _classify_yaml(data: Dict[str, Any]) -> str:
    """Classify YAML content as a spec or rule mapping.

    Args:
        data: Parsed YAML mapping.
    Returns:
        "spec" or "rule".
    """
    if RULE_KEYS.intersection(data.keys()):
        rules_validator.validate_rules(data)
        return "rule"
    errors = remapper.validate_spec(data, raise_on_error=False)
    if not errors:
        return "spec"
    rules_validator.validate_rules(data)
    return "rule"


def _extract_transforms_source(spec_data: Dict[str, Any]) -> List[str]:
    """Collect transforms_source entries from a spec mapping.

    Args:
        spec_data: Spec mapping.

    Returns:
        List of transforms source paths.
    """
    sources: List[str] = []
    meta = spec_data.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        src = meta["transforms_source"]
        if isinstance(src, str):
            sources.append(src)
        elif isinstance(src, list) and all(isinstance(item, str) for item in src):
            sources.extend(src)
        else:
            raise ValueError("transforms_source must be a string or list of strings.")
    for value in spec_data.values():
        if not isinstance(value, dict):
            continue
        child_meta = value.get("__meta__")
        if isinstance(child_meta, dict) and child_meta.get("transforms_source"):
            src = child_meta["transforms_source"]
            if isinstance(src, str):
                sources.append(src)
            elif isinstance(src, list) and all(isinstance(item, str) for item in src):
                sources.extend(src)
            else:
                raise ValueError("transforms_source must be a string or list of strings.")
    return sources


def _collect_transforms_sources(spec_path: Path, stack: Optional[Set[Path]] = None) -> Set[str]:
    """Collect transforms_source entries from a spec file, including includes.

    Args:
        spec_path: Spec YAML path.
        stack: Tracks visited specs to avoid cycles.

    Returns:
        Set of transforms_source entries.
    """
    if stack is None:
        stack = set()
    spec_path = spec_path.resolve()
    if spec_path in stack:
        return set()
    stack.add(spec_path)
    try:
        spec_data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec_data, dict):
            return set()
        sources = set(_extract_transforms_source(spec_data))
        meta = spec_data.get("__meta__")
        include_list: List[str] = []
        if isinstance(meta, dict) and "include" in meta:
            include = meta.get("include")
            if isinstance(include, str):
                include_list = [include]
            elif isinstance(include, list) and all(isinstance(item, str) for item in include):
                include_list = include
        for item in include_list:
            inc_path = Path(item)
            if not inc_path.is_absolute():
                inc_path = (spec_path.parent / inc_path).resolve()
            if not inc_path.exists():
                logger.warning("Spec include not found while listing: %s", inc_path)
                continue
            sources.update(_collect_transforms_sources(inc_path, stack))
        return sources
    finally:
        stack.remove(spec_path)


def _update_transforms_source(spec_data: Dict[str, Any], value: List[str]) -> None:
    """Rewrite transforms_source fields inside a spec mapping.

    Args:
        spec_data: Spec mapping to update in place.
        value: New transforms_source path(s).
    """
    meta = spec_data.get("__meta__")
    if isinstance(meta, dict) and meta.get("transforms_source"):
        meta["transforms_source"] = value[0] if len(value) == 1 else value
    for section in spec_data.values():
        if not isinstance(section, dict):
            continue
        section_meta = section.get("__meta__")
        if isinstance(section_meta, dict) and section_meta.get("transforms_source"):
            section_meta["transforms_source"] = value[0] if len(value) == 1 else value


def _install_transforms_from_spec(
    spec_data: Dict[str, Any],
    *,
    base_dir: Optional[Path],
    target_spec: Path,
    root: Optional[Union[str, Path]],
) -> Tuple[List[Path], bool]:
    """Install transforms referenced by a spec and rewrite paths.

    Args:
        spec_data: Spec mapping to inspect and update.
        base_dir: Base directory used to resolve relative paths.
        target_spec: Installed spec file path.
        root: Optional config root override.

    Returns:
        Tuple of (installed_paths, updated_flag).
    """
    sources = _extract_transforms_source(spec_data)
    if not sources:
        return [], False
    paths = config_core.paths(root=root)
    installed: List[Path] = []
    rel_paths: List[str] = []
    for src in sources:
        src_path = Path(src)
        target = paths.transforms_dir / src_path.name
        if base_dir is not None:
            candidate = (base_dir / src_path).resolve()
            if not candidate.exists():
                raise FileNotFoundError(candidate)
            _write_file(target, candidate.read_text(encoding="utf-8"))
        elif src_path.is_absolute():
            if not src_path.exists():
                raise FileNotFoundError(src_path)
            _write_file(target, src_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(src_path)
        rel_paths.append(os.path.relpath(target, start=target_spec.parent))
        installed.append(target)
        logger.info("Installed transforms: %s", target)
    _update_transforms_source(spec_data, rel_paths)
    return installed, True


def _resolve_spec_path(use: str, base: Path) -> Path:
    """Resolve rule `use` values into absolute spec paths.

    Args:
        use: Rule `use` value.
        base: Config root directory.

    Returns:
        Absolute spec path.
    """
    candidate = Path(use)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == "specs":
        return base / candidate
    return base / "specs" / candidate


def _ensure_rule_specs_present(rule_data: Dict[str, Any], *, root: Optional[Union[str, Path]]) -> None:
    """Ensure rule references point to installed specs.

    Args:
        rule_data: Rule mapping to inspect.
        root: Optional config root override.
    """
    base = config_core.resolve_root(root)
    for key in RULE_KEYS:
        if key == "converter_entrypoint":
            continue
        for item in rule_data.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            use = item.get("use")
            if not isinstance(use, str):
                continue
            spec_path = _resolve_spec_path(use, base)
            if not spec_path.exists():
                raise FileNotFoundError(
                    f"{spec_path} not found. Install the spec before adding rules."
                )


def _load_rule_entries(rules_dir: Path) -> List[Dict[str, str]]:
    """Load rule metadata for listing.

    Args:
        rules_dir: Directory containing rule YAML files.

    Returns:
        List of rule metadata entries.
    """
    entries: List[Dict[str, str]] = []
    if not rules_dir.exists():
        return entries
    files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))
    for path in sorted(files):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for key in RULE_KEYS:
            for item in data.get(key, []) or []:
                if not isinstance(item, dict):
                    continue
                entries.append(
                    {
                        "file": path.name,
                        "category": key,
                        "name": str(item.get("name", "")),
                        "description": str(item.get("description", "")),
                        "use": str(item.get("use", "")),
                    }
                )
    return entries


def _spec_categories_from_rules(rule_entries: List[Dict[str, str]]) -> Dict[str, str]:
    """Derive spec category labels from rule entries.

    Args:
        rule_entries: Rule metadata entries.

    Returns:
        Mapping of spec filename to category label.
    """
    mapping: Dict[str, Set[str]] = {}
    for entry in rule_entries:
        category = entry.get("category", "")
        if category not in {"info_spec", "metadata_spec"}:
            continue
        use = entry.get("use", "")
        if not use:
            continue
        spec_name = Path(use).name if use else ""
        if not spec_name:
            continue
        mapping.setdefault(spec_name, set()).add(category)
    return {name: ", ".join(sorted(cats)) for name, cats in mapping.items()}


def _load_spec_meta(path: Path) -> Dict[str, str]:
    """Load __meta__ name/description from a spec file.

    Args:
        path: Spec file path.

    Returns:
        Mapping with optional name/description.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    meta = data.get("__meta__")
    if not isinstance(meta, dict):
        return {}
    name = meta.get("name")
    desc = meta.get("description")
    out: Dict[str, str] = {}
    if isinstance(name, str):
        out["name"] = name
    if isinstance(desc, str):
        out["description"] = desc
    return out


def _write_file(target: Path, content: str) -> None:
    """Write text content to a target path.

    Args:
        target: Output file path.
        content: Text content to write.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


__all__ = [
    "add",
    "add_rule_data",
    "add_spec_data",
    "install_examples",
    "list_installed",
    "remove",
]

def __dir__() -> List[str]:
    return sorted(__all__)
