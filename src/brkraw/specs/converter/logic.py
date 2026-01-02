from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Dict, Union

from ...core.entrypoints import list_entry_points
from .validator import validate_entrypoint

DEFAULT_GROUP = "brkraw.converter"


def resolve_entrypoint(
    entrypoint: Union[Mapping[str, Callable[..., Any]], str],
    *,
    group: str = DEFAULT_GROUP,
) -> Dict[str, Callable[..., Any]]:
    if isinstance(entrypoint, str):
        matches = list_entry_points(group, entrypoint)
        if not matches:
            raise LookupError(
                f"Converter entry point not found: {entrypoint!r} (group={group!r})"
            )
        entry = matches[0].load()
        validate_entrypoint(entry)
        return dict(entry)
    validate_entrypoint(entrypoint)
    return dict(entrypoint)


__all__ = ["DEFAULT_GROUP", "resolve_entrypoint"]
