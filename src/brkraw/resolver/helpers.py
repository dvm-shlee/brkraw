from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING, Union, Tuple, List, Any
if TYPE_CHECKING:
    from ..dataclasses import Study, Scan, Reco


def get_reco(obj: "Scan", reco_id):
    if reco_id not in obj.avail.keys():
        raise KeyError('reco_id')
    return obj.avail[reco_id]


def get_file(obj: Union["Study", "Scan", "Reco"], basename: str):
    if not hasattr(obj, basename):
        raise FileNotFoundError(basename)
    else:
        key = obj._full_path(basename)
        if key in obj._cache.keys():
            obj._cache.pop(key, None)
    return getattr(obj, f'file_{basename}')

def return_alt_val_if_none(val: object, alt_val: object) -> object:
    if val is None:
        return alt_val
    return val

def strip_comment(raw_comment: str):
    return raw_comment.strip('<>').strip()


def swap_element(obj: List[Any], index1: int, index2: int) -> List[Any]:
    new_obj = obj[:]
    new_obj[index1], new_obj[index2] = new_obj[index2], new_obj[index1]
    return new_obj
