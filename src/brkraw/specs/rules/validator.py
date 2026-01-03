from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Optional
from importlib import resources

try:
    resources.files  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - fallback for Python 3.8
    import importlib_resources as resources  # type: ignore[assignment]

import yaml

from ...core.entrypoints import list_entry_points

CONVERTER_GROUP = "brkraw.converter"

def _load_schema() -> Dict[str, Any]:
    if __package__ is None:
        raise RuntimeError("Package context required to load rules schema.")
    with resources.files("brkraw.schema").joinpath("rules.yaml").open(
        "r", encoding="utf-8"
    ) as handle:
        return yaml.safe_load(handle)


def validate_rules(
    rule_data: Dict[str, Any],
    schema_path: Optional[Path] = None,
) -> None:
    """Validate rule mappings against schema and entrypoint availability.

    Args:
        rule_data: Parsed rule mapping to validate.
        schema_path: Optional rules schema path override.
    """
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required to validate rule files.") from exc
    schema = (
        _load_schema()
        if schema_path is None
        else yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    )
    jsonschema.Draft202012Validator(schema).validate(rule_data)
    _validate_converter_entrypoints(rule_data)


def _validate_converter_entrypoints(rule_data: Dict[str, Any]) -> None:
    """Ensure converter_entrypoint references resolve to installed entry points."""
    missing: List[str] = []
    items = rule_data.get("converter_entrypoint", [])
    if not items:
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        use = item.get("use")
        if not isinstance(use, str):
            continue
        if not list_entry_points(CONVERTER_GROUP, use):
            missing.append(use)
    if missing:
        missing_text = ", ".join(sorted(set(missing)))
        raise ValueError(
            "converter_entrypoint references missing entry points: "
            f"{missing_text} (group={CONVERTER_GROUP})"
        )
