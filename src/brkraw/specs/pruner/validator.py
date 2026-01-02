from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
import importlib.resources as resources

import yaml


def validate_prune_spec(spec: Mapping[str, Any], schema_path: Optional[Path] = None) -> List[str]:
    """Validate a prune spec against schema.

    Args:
        spec: Parsed prune spec mapping.
        schema_path: Optional schema path override.

    Returns:
        List of validation error messages (empty when valid).
    """
    errors: List[str] = []
    try:
        import jsonschema
    except Exception:
        errors = _validate_spec_minimal(spec)
    else:
        schema = _load_schema(schema_path)
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(spec):
            path = ".".join(str(p) for p in err.path)
            prefix = f"spec.{path}" if path else "spec"
            errors.append(f"{prefix}: {err.message}")

    if errors:
        raise ValueError("Invalid prune spec:\n" + "\n".join(errors))
    return errors


def _load_schema(schema_path: Optional[Path]) -> Dict[str, Any]:
    if schema_path is not None:
        return yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    if __package__ is None:
        raise RuntimeError("Package context required to load pruner schema.")
    with resources.files("brkraw.schema").joinpath("pruner.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def _validate_spec_minimal(spec: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(spec, Mapping):
        errors.append("spec: must be a mapping.")
        return errors

    files = spec.get("files")
    if not isinstance(files, list) or not files:
        errors.append("spec.files: must be a non-empty list.")
    else:
        for idx, item in enumerate(files):
            if not isinstance(item, (str, int)):
                errors.append(f"spec.files[{idx}]: must be string or int.")

    mode = spec.get("mode", "keep")
    if mode not in {"keep", "drop"}:
        errors.append("spec.mode: must be 'keep' or 'drop'.")

    update_params = spec.get("update_params")
    if update_params is not None and not isinstance(update_params, Mapping):
        errors.append("spec.update_params: must be a mapping.")

    dir_rules = spec.get("dir_rules")
    if dir_rules is not None and not isinstance(dir_rules, list):
        errors.append("spec.dir_rules: must be a list.")
    if isinstance(dir_rules, list):
        for idx, rule in enumerate(dir_rules):
            if not isinstance(rule, Mapping):
                errors.append(f"spec.dir_rules[{idx}]: must be a mapping.")
                continue
            if rule.get("mode") not in {"keep", "drop"}:
                errors.append(f"spec.dir_rules[{idx}].mode: must be 'keep' or 'drop'.")
            level = rule.get("level")
            if not isinstance(level, int) or level < 1:
                errors.append(f"spec.dir_rules[{idx}].level: must be int >= 1.")
            dirs = rule.get("dirs")
            if not isinstance(dirs, list) or not dirs:
                errors.append(f"spec.dir_rules[{idx}].dirs: must be a non-empty list.")

    add_root = spec.get("add_root")
    if add_root is not None and not isinstance(add_root, bool):
        errors.append("spec.add_root: must be boolean.")

    root_name = spec.get("root_name")
    if root_name is not None and not isinstance(root_name, str):
        errors.append("spec.root_name: must be a string.")

    source = spec.get("source")
    if source is not None and not isinstance(source, str):
        errors.append("spec.source: must be a string.")

    dest = spec.get("dest")
    if dest is not None and not isinstance(dest, str):
        errors.append("spec.dest: must be a string.")

    return errors


__all__ = ["validate_prune_spec"]
