from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Mapping

from ..core.fs import DatasetFS
from .node import DatasetNode
from .reco import Reco


@dataclass
class Scan(DatasetNode):
    fs: DatasetFS
    scan_id: int
    relroot: str
    recos: Dict[int, Reco] = field(default_factory=dict)
    _cache: Dict[str, object] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_fs(cls, fs: DatasetFS, scan_id: int, relroot: str) -> "Scan":
        scan = cls(fs, scan_id, relroot)
        scan._index_recos(top=relroot)
        return scan

    def _index_recos(self, top: Optional[str] = None) -> None:
        """Find pdata/<reco_id> dirs under this scan and attach PVReco."""
        import re
        pdata_prefix = f"{self.relroot}/pdata"

        for dirpath, dirnames, filenames in self.fs.walk(top=top or ""):
            rel = self.fs.strip_anchor(dirpath)
            if not rel.startswith(pdata_prefix):
                continue
            m = re.fullmatch(rf"{self.relroot}/pdata/(\d+)", rel)
            if not m:
                continue
            reco_id = int(m.group(1))
            self.recos[reco_id] = Reco.from_fs(
                fs=self.fs,
                scan=self,
                reco_id=reco_id,
                relroot=rel,
            )

    def get_reco(self, reco_id: int) -> Reco:
        return self.recos[reco_id]

    @property
    def avail(self) -> Mapping[int, Reco]:
        return {k: self.recos[k] for k in sorted(self.recos)}

    def __repr__(self) -> str:
        method_val = None
        try:
            method_obj = getattr(self, "method")
            method_val = getattr(method_obj, "Method", None)
        except Exception:
            method_val = None
        method_part = f" Method={method_val!r}" if method_val is not None else ""
        return f"Scan(id={self.scan_id} rel='/{self.relroot}'{method_part})"

    __all__ = ['Scan']
