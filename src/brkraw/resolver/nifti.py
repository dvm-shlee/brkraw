from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Optional, Literal, Tuple, Sequence, cast, Any
import logging
import numpy as np
from nibabel.spatialimages import HeaderDataError

if TYPE_CHECKING:
    from .image import ResolvedImage
    from nibabel.nifti1 import Nifti1Image

SLOPEMODE = Literal['header', 'dataobj', 'ignore']
TUNIT = Literal['sec', 'msec', 'usec', 'hz', 'ppm', 'rads']
XYZUNIT = Literal['unknown', 'meter', 'mm', 'micron']
XYZTUnit = Tuple[XYZUNIT, TUNIT]
DimInfo = Tuple[Optional[int], Optional[int], Optional[int]]

logger = logging.getLogger("brkraw")

class Nifti1HeaderContents(TypedDict, total=False):
    flip_x: bool
    slice_code: int
    slope_inter: Tuple[float, float]
    time_step: Optional[float]
    slice_duration: Optional[float]
    xyzt_unit: XYZTUnit
    qform: np.ndarray
    sform: np.ndarray
    qform_code: int
    sform_code: int
    dim_info: DimInfo
    slice_start: int
    slice_end: int
    intent_code: int
    intent_name: str
    descrip: str
    aux_file: str
    cal_min: float
    cal_max: float
    pixdim: Sequence[float]


def _coerce_scalar(value, *, name: str) -> float:
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        if value.size > 1:
            logger.debug("NIfTI %s array has multiple values; using first element.", name)
        return float(value.flat[0])
    if isinstance(value, (list, tuple)):
        if not value:
            return 0.0
        if len(value) > 1:
            logger.debug("NIfTI %s list has multiple values; using first element.", name)
        seq = cast(Sequence[float], value)
        return float(seq[0])
    return float(value)


def _coerce_int(value, *, name: str) -> int:
    return int(_coerce_scalar(value, name=name))


def _get_slice_code(sliceorder_scheme: Optional[str]) -> int:
    if sliceorder_scheme is None or sliceorder_scheme == "User_defined_slice_scheme":
        return 0
    if sliceorder_scheme == "Sequential":
        return 1
    elif sliceorder_scheme == 'Reverse_sequential':
        return 2
    elif sliceorder_scheme == 'Interlaced':
        return 3
    elif sliceorder_scheme == 'Reverse_interlacesd':
        return 4
    elif sliceorder_scheme == 'Angiopraphy':
        return 5
    else:
        return 0


def _set_dataobj(niiobj: "Nifti1Image", dataobj: np.ndarray) -> None:
    """Update the NIfTI data object, falling back to direct assignment."""
    setter = getattr(niiobj, "set_dataobj", None)
    if callable(setter):
        setter(dataobj)
    else:
        object.__setattr__(niiobj, "_dataobj", dataobj)


def resolve(
    image_info: "ResolvedImage", 
    flip_x: bool = False, 
    xyz_units: "XYZUNIT" = 'mm', 
    t_units: "TUNIT" = 'sec'
) -> Nifti1HeaderContents:
    
    sliceorder_scheme = image_info['sliceorder_scheme']
    num_cycles = image_info['num_cycles']
    
    slice_code = _get_slice_code(sliceorder_scheme)
    if slice_code == 0:
        logger.debug(
            "Failed to identify compatible 'slice_code'. "
            "Please use this header information with care in case slice timing correction is needed."
        )
    
    if num_cycles > 1:
        time_step = cast(float, image_info['time_per_cycle']) / 1000.0
        num_slices = image_info['dataobj'].shape[2]
        slice_duration = time_step / num_slices
    else:
        time_step = None
        slice_duration = None
    slope = image_info['slope']
    offset = image_info['offset']
    result: Nifti1HeaderContents = {
        'flip_x': flip_x,
        'slice_code': slice_code,
        'slope_inter': (slope, offset),
        'time_step': time_step,
        'slice_duration': slice_duration,
        'xyzt_unit': (xyz_units, t_units)
    }
    return result


def update(
    niiobj: "Nifti1Image",
    nifti1header_contents: Nifti1HeaderContents,
    slope_mode: SLOPEMODE = 'header',
):
    qform_code = nifti1header_contents.get("qform_code")
    sform_code = nifti1header_contents.get("sform_code")
    

    for c, val in nifti1header_contents.items():
        if val is None or c in ('qform_code', 'sform_code'):
            continue
        if c == 'flip_x':
            niiobj.header.default_x_flip = bool(val)
        elif c == "slice_code":
            if _coerce_int(val, name="slice_code") != 0:
                niiobj.header['slice_code'] = _coerce_int(val, name="slice_code")
        elif c == "slope_inter":
            pair = cast(Sequence[float], val)
            slope_val = _coerce_scalar(pair[0], name="slope")
            inter_val = _coerce_scalar(pair[1], name="intercept")
            if slope_mode == 'header':
                niiobj.header.set_slope_inter(slope_val, inter_val)
            elif slope_mode == 'dataobj':
                dataobj = np.asarray(niiobj._dataobj)
                _set_dataobj(niiobj, dataobj * slope_val + inter_val)
            else:
                pass
            niiobj.header.set_data_dtype(np.asarray(niiobj._dataobj).dtype)
        elif c == "time_step":
            niiobj.header['pixdim'][4] = _coerce_scalar(val, name="time_step")
        elif c == "slice_duration":
            slice_dim = niiobj.header.get_dim_info()[2]
            if slice_dim is None:
                logger.debug("Skipping slice_duration: slice dimension not set.")
                continue
            try:
                niiobj.header.set_slice_duration(_coerce_scalar(val, name="slice_duration"))
            except HeaderDataError as exc:
                logger.debug("Skipping slice_duration: %s", exc)
        elif c == "xyzt_unit":
            units = cast(Sequence[str], val)
            niiobj.header.set_xyzt_units(*units)
        elif c == "qform":
            if qform_code is None:
                niiobj.header.set_qform(val, 1)
            else:
                niiobj.header.set_qform(val, int(qform_code))
        elif c == "sform":
            if sform_code is None:
                niiobj.header.set_sform(val, 1)
            else:
                niiobj.header.set_sform(val, int(sform_code))
        elif c == "dim_info":
            dims = cast(Sequence[Optional[int]], val)
            niiobj.header.set_dim_info(*dims)
        elif c == "slice_start":
            niiobj.header['slice_start'] = _coerce_int(val, name="slice_start")
        elif c == "slice_end":
            niiobj.header['slice_end'] = _coerce_int(val, name="slice_end")
        elif c == "intent_code":
            niiobj.header['intent_code'] = _coerce_int(val, name="intent_code")
        elif c == "intent_name":
            niiobj.header['intent_name'] = str(val)
        elif c == "descrip":
            niiobj.header['descrip'] = str(val)
        elif c == "aux_file":
            niiobj.header['aux_file'] = str(val)
        elif c == "cal_min":
            niiobj.header['cal_min'] = _coerce_scalar(val, name="cal_min")
        elif c == "cal_max":
            niiobj.header['cal_max'] = _coerce_scalar(val, name="cal_max")
        elif c == "pixdim":
            if val:
                niiobj.header['pixdim'][1:1 + len(val)] = val # pyright: ignore[reportArgumentType]
        else:
            raise KeyError(f"Unknown NIfTI header field: {c}")
    return niiobj


__all__ = [
    'resolve',
    'update'
]
