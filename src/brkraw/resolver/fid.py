"""
Locate and load Bruker Paravision FID/rawdata for custom reconstruction.

This helper finds the FID (or rawdata) file in a Scan node, resolves the
expected NumPy dtype from metadata, and returns a flat NumPy array. Optional
byte offsets/sizes allow partial reads for debugging or incremental loading.
Returns None when required files or dtype metadata are missing.
"""
from __future__ import annotations


from warnings import warn
from .datatype import resolve as datatype_resolver
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..dataclasses import Scan

import numpy as np

def get_fid(scan: "Scan"):
    """Return the first FID/rawdata candidate in a scan, warning on multiples."""
    fid_candidates = []
    for fileobj in scan.iterdir():
        if 'fid' in fileobj.name or 'rawdata' in fileobj.name:
            fid_candidates.append(fileobj)
    if len(fid_candidates) == 0:
        return None
    elif len(fid_candidates) > 1:
        warn('Multiple FID file candidates found. Take first one.')
    return fid_candidates[0]


def resolve(
    scan: "Scan",
    buffer_start: Optional[int] = None,
    buffer_size: Optional[int] = None,
    *,
    as_complex: bool = True,
) -> Optional[np.ndarray]:
    """Load FID as a NumPy array for reconstruction workflows.

    Args:
        scan: Scan node containing the FID/rawdata file.
        buffer_start: Optional byte offset to start reading (default: 0).
        buffer_size: Optional number of bytes to read (default: entire file).
        as_complex: When True (default), interpret interleaved real/imag pairs
            as complex samples. When False, return the raw 1D array.
    
    Returns:
        1D NumPy array of complex samples (or raw when as_complex=False), or
        None when file/dtype is missing.

    Raises:
        ValueError: If buffer_start or buffer_size is negative.
    """
    fid_entry = get_fid(scan)
    if fid_entry is None:
        return None

    dtype_info = datatype_resolver(scan)
    if not dtype_info or 'dtype' not in dtype_info:
        return None

    dtype = np.dtype(dtype_info['dtype'])
    start = 0 if buffer_start is None else int(buffer_start)
    size = None if buffer_size is None else int(buffer_size)

    if start < 0 or (size is not None and size < 0):
        raise ValueError("buffer_start and buffer_size must be non-negative")

    with fid_entry.open() as f:
        f.seek(start)
        raw = f.read() if size is None else f.read(size)
    data = np.frombuffer(raw, dtype)

    if not as_complex:
        return data

    if data.size % 2 != 0:
        raise ValueError("FID data length is not even; cannot form complex pairs.")

    real = data[0::2]
    imag = data[1::2]
    return real.astype(np.float32, copy=False) + 1j * imag.astype(np.float32, copy=False)


__all__ = [
    'resolve'
]
