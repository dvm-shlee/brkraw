from __future__ import annotations

import importlib.metadata
from typing import Optional, List, Any, cast


def list_entry_points(group: str, name: Optional[str] = None) -> List[importlib.metadata.EntryPoint]:
    """List installed entry points for a group/name.

    Args:
        group: Entry point group name.
        name: Optional entry point name filter.

    Returns:
        List of matching entry points.
    """
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        eps_any = cast(Any, eps)
        if name is not None:
            return list(eps_any.select(group=group, name=name))
        return list(eps_any.select(group=group))
    if name is not None:
        return [ep for ep in eps.get(group, []) if ep.name == name]  # type: ignore[call-arg,attr-defined]
    return list(eps.get(group, []))  # type: ignore[call-arg,attr-defined]
