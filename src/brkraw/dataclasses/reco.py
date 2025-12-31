from __future__ import annotations
from dataclasses import dataclass, field

from ..core.fs import DatasetFS
from .node import DatasetNode
from typing import TYPE_CHECKING, Dict
if TYPE_CHECKING:
    from .scan import Scan


@dataclass
class Reco(DatasetNode):
    fs: DatasetFS
    scan_id: int
    reco_id: int
    relroot: str          # e.g.: "3/pdata/1"
    _cache: Dict[str, object] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_fs(cls, fs: DatasetFS, scan: "Scan", reco_id: int, relroot: str) -> "Reco":
        return cls(fs=fs, scan_id=scan.scan_id, reco_id=reco_id, relroot=relroot)

    def __repr__(self) -> str:
        image_type = None
        try:
            reco_obj = getattr(self, "reco")
            image_type = getattr(reco_obj, "RECO_image_type", None)
        except Exception:
            image_type = None
        type_part = f" type={image_type!r}" if image_type is not None else ""
        return f"Reco(scan_id={self.scan_id} id={self.reco_id} rel='/{self.relroot}'{type_part})"

__all__ = ['Reco']
