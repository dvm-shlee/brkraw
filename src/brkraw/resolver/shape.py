"""
Resolve Paravision geometry metadata into lightweight dictionaries.

This module reads parameter files from `Scan`/`Reco` nodes and normalizes
image geometry (dims, FOV, voxel size), frame-group structure, slice-pack
layout, and cycle timing into small TypedDicts. Helpers can be called
independently or via `resolve`, which bundles the pieces into a single report.
Returns None when required metadata is missing.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Tuple, Literal, TypedDict, Sequence, Union, cast 
from dataclasses import dataclass
from math import prod
import re
import numpy as np
from .helpers import get_reco, get_file, strip_comment
if TYPE_CHECKING:
    from ..dataclasses import Reco, Scan
    from ..core.parameters import Parameters

FrameGroupEntry = Tuple[int, str, str, int, int]
FrameGroupOrder = List[FrameGroupEntry]

class ResolvedImageInfo(TypedDict):
    dim: Optional[int]
    dim_desc: Optional[Sequence[str]]
    fov: Optional[List[float]]
    shape: Optional[List[int]]
    resol: Optional[List[float]]
    unit: Literal["mm"]


class ResolvedFrameGroup(TypedDict):
    type: Optional[Union[str, List[str]]]
    id: List[str]
    shape: List[int]
    comments: List[Optional[str]]
    dependent_vals: List[List[object]]
    size: int


class ResolvedCycle(TypedDict):
    num_cycles: int
    time_step: float
    unit: str


class ResolvedShape(TypedDict):
    shape: List[int]
    shape_desc: List[str]
    num_cycle: int
    sliceorder_scheme: Optional[str]
    objs: ResolvedCollection


@dataclass
class ResolvedCollection:
    image: Optional[ResolvedImageInfo]
    frame_group: Optional[ResolvedFrameGroup]
    cycle: Optional[ResolvedCycle]

    def __repr__(self):
        resolved = []
        if self.image:
            resolved.append('image')
        if self.frame_group:
            resolved.append('frame_group')
        if self.cycle:
            resolved.append('cycle')
        resolved = ', '.join(resolved)
        return f'<Resolved: {resolved}>'


def resolve_image_info(visu_pars: "Parameters") -> Optional[ResolvedImageInfo]:
    """Return core image geometry from visu_pars (in millimeters).

    Args:
        visu_pars: Paravision visu_pars Parameter object from Reco.

    Returns:
        ImageInfo with dim, fov, shape, resolution, and unit; None if missing.
    """
    dim = visu_pars.get('VisuCoreDim')
    dim_desc = visu_pars.get('VisuCoreDimDesc')
    fov_arr = visu_pars.get('VisuCoreExtent')
    shape_arr = visu_pars.get('VisuCoreSize')
    resol_arr = np.divide(fov_arr, shape_arr) if (fov_arr is not None and shape_arr is not None) else None
    return {
        'dim': cast(Optional[int], dim),
        'dim_desc': dim_desc.tolist() if isinstance(dim_desc, np.ndarray) else cast(Optional[Sequence[str]], dim_desc),
        'fov': fov_arr.tolist() if isinstance(fov_arr, np.ndarray) else cast(Optional[List[float]], fov_arr),
        'shape': shape_arr.tolist() if isinstance(shape_arr, np.ndarray) else cast(Optional[List[int]], shape_arr),
        'resol': resol_arr.tolist() if isinstance(resol_arr, np.ndarray) else cast(Optional[List[float]], resol_arr),
        'unit': 'mm',
    }


def resolve_frame_group(visu_pars: "Parameters") -> Optional[ResolvedFrameGroup]:
    """Parse VisuCore frame-group description into a normalized structure.

    Args:
        visu_pars: Paravision visu_pars Parameter object from Reco.

    Returns:
        FrameGroupInfo with ids, shapes, comments, dependent values, and size;
        None if absent.
    """
    if not visu_pars.get('VisuFGOrderDescDim'):
        return None

    fg_order_raw = visu_pars.get('VisuFGOrderDesc')
    if fg_order_raw is None:
        return None

    def _normalize_order(raw: object) -> FrameGroupOrder:
        if not isinstance(raw, (list, tuple)):
            raise TypeError("VisuFGOrderDesc")
        if raw and not isinstance(raw[0], (list, tuple)):
            return [cast(FrameGroupEntry, raw)]
        return [cast(FrameGroupEntry, item) for item in raw]
    
    def _dependent_values(start: int, count: int) -> List[object]:
        if not count:
            return []
        values = visu_pars['VisuGroupDepVals']
        return [values[start + i] for i in range(count)]
    
    fg_order = _normalize_order(fg_order_raw)
    fg_type_raw = visu_pars.get('VisuCoreFrameType')
    fg_type: Optional[Union[str, List[str]]]
    if isinstance(fg_type_raw, np.ndarray):
        fg_type = cast(List[str], fg_type_raw.tolist())
    else:
        fg_type = cast(Optional[Union[str, List[str]]], fg_type_raw)
    fg_id: List[str] = [str(entry[1]) for entry in fg_order]
    shape: List[int] = [int(entry[0]) for entry in fg_order]
    comments: List[Optional[str]] = [strip_comment(entry[2]) for entry in fg_order]
    dependent_vals: List[List[object]] = [_dependent_values(int(entry[3]), int(entry[4])) for entry in fg_order]
    
    result: ResolvedFrameGroup = {
        'type': fg_type,
        'id': fg_id,
        'shape': shape,
        'comments': comments,
        'dependent_vals': dependent_vals,
        'size': prod(shape) if shape else 0
    }
    return result


def resolve_cycle(visu_pars: "Parameters", fg_info: Optional[ResolvedFrameGroup] = None) -> Optional[ResolvedCycle]:
    """Derive cycle count and time step from frame-group metadata.

    Args:
        visu_pars: Paravision visu_pars Parameter object from Reco.
        fg_info: Optional precomputed frame-group info; computed if omitted.

    Returns:
        CycleInfo with cycle count and time step (msec); None if not applicable.
    """
    scan_time = visu_pars.get("VisuAcqScanTime") or 0
    if fg_info:
        fg_cycle = [fg_info['shape'][idx] for idx, fg in enumerate(fg_info['id']) if re.search('cycle', fg, re.IGNORECASE)]
        num_cycles = fg_cycle[-1] if fg_cycle else 1
        time_step = (scan_time / num_cycles) if num_cycles else 0
        return {
            'num_cycles': num_cycles,
            'time_step': time_step,
            'unit': 'msec',
        }
    return None


def resolve(scan: "Scan", reco_id: int = 1):
    """Resolve image, frame-group, cycle, and slice-pack metadata for a scan.

    Args:
        scan: Scan node.
        reco_id: Reco id to process.

    Returns:
        Mapping with combined shape info, descriptors, counts, and a ResolvedInfo bundle;
        None if required files are missing.
    """
    reco: "Reco" = get_reco(scan, reco_id)
    try:
        method: "Parameters" = get_file(scan, 'method')
    except FileNotFoundError:
        return None
    try:
        visu_pars: "Parameters" = get_file(reco, 'visu_pars')
    except FileNotFoundError:
        return None

    img_info = resolve_image_info(visu_pars)
    fg_info = resolve_frame_group(visu_pars)
    cycle_info = resolve_cycle(visu_pars, fg_info)
    sliceorder_scheme = method.get("PVM_ObjOrderScheme")

    shape_source = img_info['shape'] if img_info else None
    shape = list(shape_source) if shape_source else []
    dim_desc_source = img_info['dim_desc'] if img_info else None
    if isinstance(dim_desc_source, str):
        shape_desc: List[str] = [dim_desc_source]
    elif dim_desc_source:
        shape_desc = list(dim_desc_source)
    else:
        shape_desc = []
    num_cycles = cycle_info['num_cycles'] if cycle_info else 1
    fg_desc = [strip_comment(i).replace('FG_', '').strip().lower() for i in fg_info.get('id', [])] if fg_info else []

    if img_info and img_info['dim'] == 2:
        if not fg_info or (fg_info and 'slice' not in fg_desc):
            shape.extend([1])
            shape_desc.extend(['without_slice'])

    if fg_info and fg_info.get('type') != None:
        shape.extend(fg_info.get('shape', []))
        shape_desc.extend(fg_desc)
        
    result: ResolvedShape = {
        'shape': shape,
        'shape_desc': shape_desc,
        'num_cycle': num_cycles,
        'sliceorder_scheme': sliceorder_scheme,
        'objs': ResolvedCollection(
            img_info, fg_info, cycle_info
        )
    }
    return result

__all__ = [
    'resolve'
    ]
