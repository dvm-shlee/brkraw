from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, List

CONVERTER_KEYS = {"get_dataobj", "get_affine", "get_nifti1image"}


def validate_entrypoint(entrypoint: Any, *, raise_on_error: bool = True) -> List[str]:
    errors: List[str] = []
    if not isinstance(entrypoint, Mapping):
        errors.append("converter_entrypoint: must be a mapping.")
    else:
        for key, value in entrypoint.items():
            if key not in CONVERTER_KEYS:
                errors.append(f"converter_entrypoint: invalid key {key!r}.")
            if not callable(value):
                errors.append(f"converter_entrypoint[{key!r}]: must be callable.")
    if errors and raise_on_error:
        raise ValueError("Invalid converter entrypoint:\n" + "\n".join(errors))
    return errors
