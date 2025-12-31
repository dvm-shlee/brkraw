"""
Load Paravision `2dseq` data into a NumPy array with geometry metadata.

This resolver reads dtype/slope/offset and shape info for a given `Scan`/`Reco`,
then reshapes the `2dseq` buffer (Fortran order) and normalizes axis labels so
the spatial z-axis sits at index 2. Returns None when required metadata or
files are missing.
"""
from __future__ import annotations


from typing import TYPE_CHECKING, Optional, Sequence, TypedDict, List, Tuple
from .datatype import resolve as datatype_resolver
from .shape import resolve as shape_resolver
from .helpers import get_reco, get_file, swap_element
import numpy as np

if TYPE_CHECKING:
    from ..dataclasses import Scan, Reco
    from .shape import ResolvedShape
    from .shape import ResolvedCycle


class ResolvedImage(TypedDict):
    dataobj: np.ndarray
    slope: float
    offset: float
    shape_desc: List[str]
    sliceorder_scheme: Optional[str]
    num_cycles: int
    time_per_cycle: Optional[float]


Z_AXIS_DESCRIPTORS = {'spatial', 'slice', 'without_slice'}


def _find_z_axis_candidate(shape_desc: Sequence[str]) -> Optional[int]:
    """Return the first spatial z-axis descriptor index found at/after position 2."""
    for idx, desc in enumerate(shape_desc):
        if idx < 2:
            continue
        if desc in Z_AXIS_DESCRIPTORS:
            return idx
    return None


def _normalize_zaxis_descriptor(shape_desc: List[str]) -> List[str]:
    """Ensure the z-axis descriptor uses 'slice' to represent spatial depth."""
    normalized = shape_desc[:]
    if normalized[2] == 'without_slice':
        normalized[2] = 'slice'
    return normalized


def _validate_swapped_axes(
    dataobj: np.ndarray,
    expected_shape: Sequence[int],
    shape_desc: List[str],
    original_zaxis_desc: str,
    swapped_idx: int,
):
    """Validate shape/descriptor invariants after moving spatial z-axis into position 2."""
    if dataobj.shape != tuple(expected_shape):
        raise ValueError(f"data shape {dataobj.shape} does not match expected {tuple(expected_shape)} after z-axis swap")
    if len(expected_shape) != len(shape_desc):
        raise ValueError("shape and shape_desc length mismatch after z-axis normalization")
    if shape_desc[swapped_idx] != original_zaxis_desc:
        raise ValueError(f"axis {swapped_idx} descriptor mismatch after swap; expected '{original_zaxis_desc}'")
    if shape_desc[2] not in Z_AXIS_DESCRIPTORS:
        raise ValueError(f"z-axis descriptor '{shape_desc[2]}' is invalid; expected one of {sorted(Z_AXIS_DESCRIPTORS)}")


def ensure_3d_spatial_data(dataobj: np.ndarray, shape_info: "ResolvedShape") -> Tuple[np.ndarray, List[str]]:
    """
    Normalize data and descriptors so the spatial z-axis sits at index 2.

    Swaps axes when needed to place the first spatial z-axis descriptor at
    position 2 and rewrites 'without_slice' to 'slice' for clarity.

    Raises:
        ValueError: When data dimensionality and shape_desc disagree or z-axis
            descriptor is missing.
    """
    shape = shape_info['shape']
    shape_desc = list(shape_info['shape_desc'])

    if dataobj.ndim != len(shape_desc):
        raise ValueError(f"dataobj.ndim ({dataobj.ndim}) and shape_desc length ({len(shape_desc)}) do not match")

    if dataobj.ndim < 3 or len(shape_desc) < 3:
        return dataobj, shape_desc

    if shape_desc[2] in Z_AXIS_DESCRIPTORS:
        return dataobj, _normalize_zaxis_descriptor(shape_desc)

    zaxis_candi_idx = _find_z_axis_candidate(shape_desc)
    if zaxis_candi_idx is None:
        raise ValueError(f"z-axis descriptor not found in shape_desc starting at index 2: {shape_desc}")

    pre_zaxis_desc = shape_desc[2]
    new_dataobj = np.swapaxes(dataobj, 2, zaxis_candi_idx)
    new_shape = swap_element(shape, 2, zaxis_candi_idx)
    new_shape_desc = swap_element(shape_desc, 2, zaxis_candi_idx)

    _validate_swapped_axes(new_dataobj, new_shape, new_shape_desc, pre_zaxis_desc, zaxis_candi_idx)

    normalized_shape_desc = _normalize_zaxis_descriptor(new_shape_desc)
    return new_dataobj, normalized_shape_desc


def _read_2dseq_data(reco: "Reco", dtype: np.dtype, shape: Sequence[int]) -> np.ndarray:
    """Read 2dseq file into a Fortran-ordered NumPy array with shape validation."""
    expected_size = int(np.prod(shape)) * np.dtype(dtype).itemsize
    with get_file(reco, "2dseq") as f:
        f.seek(0)
        raw = f.read()
    if len(raw) != expected_size:
        raise ValueError(f"2dseq size mismatch: expected {expected_size} bytes for shape {shape}, got {len(raw)}")
    try:
        return np.frombuffer(raw, dtype).reshape(shape, order="F")
    except ValueError as exc:
        raise ValueError(f"failed to reshape 2dseq buffer to shape {shape}") from exc


def _normalize_cycle_info(cycle_info: Optional["ResolvedCycle"]) -> Tuple[int, Optional[float]]:
    """Normalize cycle info and provide safe defaults when metadata is absent."""
    if not cycle_info:
        return 1, None
    return int(cycle_info['num_cycles']), cycle_info.get('time_step')


def resolve(scan: "Scan", reco_id: int = 1) -> Optional[ResolvedImage]:
    """Load 2dseq as a NumPy array with associated metadata.

    Args:
        scan: Scan node containing the target reco.
        reco_id: Reco identifier to read (default: 1).

    Returns:
        ImageResolveResult with:
            - dataobj: NumPy array reshaped using Fortran order.
            - slope/offset: intensity scaling.
            - shape_desc: normalized descriptors with spatial z-axis at index 2.
            - slice/cycle metadata.
        None if required metadata or files are missing; raises ValueError on
        inconsistent metadata.
    """
    reco: "Reco" = get_reco(scan, reco_id)

    dtype_info = datatype_resolver(reco)
    shape_info = shape_resolver(scan, reco_id=reco_id)
    if not dtype_info or not shape_info:
        return None

    dtype = np.dtype(dtype_info["dtype"])
    slope = dtype_info["slope"]
    if slope is None:
        slope = 1.0
    offset = dtype_info["offset"]
    if offset is None:
        offset = 0.0
    shape = shape_info["shape"]

    try:
        dataobj = _read_2dseq_data(reco, dtype, shape)
    except FileNotFoundError:
        return None

    dataobj, shape_desc = ensure_3d_spatial_data(dataobj, shape_info)
    num_cycles, time_per_cycle = _normalize_cycle_info(shape_info['objs'].cycle)

    result: ResolvedImage = {
        # image
        'dataobj': dataobj,
        'slope': slope,
        'offset': offset,
        'shape_desc': shape_desc,
        'sliceorder_scheme': shape_info['sliceorder_scheme'],

        # cycle
        'num_cycles': num_cycles,
        'time_per_cycle': time_per_cycle,
    }
    return result

__all__ = [
    'resolve'
]
