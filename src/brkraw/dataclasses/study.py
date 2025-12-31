from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping, Union, TYPE_CHECKING, List

from ..core.fs import DatasetFS
from .node import DatasetNode
from .scan import Scan

if TYPE_CHECKING:
    from ..apps.loader.types import ScanLoader


@dataclass
class Study(DatasetNode):
    fs: DatasetFS
    relroot: str = ""
    scans: Dict[int, Scan] = field(default_factory=dict)
    _cache: Dict[str, object] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "Study":
        """Load a study rooted at path, preferring bottom-up discovery."""
        fs = DatasetFS.from_path(path)
        found = cls.discover(fs)
        if not found:
            raise ValueError(f"No Paravision study found under {path}")

        anchor = fs.anchor
        if anchor:
            for study in found:
                if study.relroot == anchor:
                    return study

        if len(found) == 1:
            return found[0]

        raise ValueError(
            f"Multiple studies found under {path}; "
            f"cannot choose automatically ({[s.relroot for s in found]})"
        )

    @classmethod
    def discover(cls, fs: DatasetFS) -> List["Study"]:
        """Bottom-up discovery using reco markers (2dseq + visu_pars)."""
        reco_dirs: List[str] = []
        for dirpath, dirnames, filenames in fs.walk():
            rel = fs.strip_anchor(dirpath)
            names = set(filenames)
            if "2dseq" in names and "visu_pars" in names:
                reco_dirs.append(rel)

        studies: Dict[str, Study] = {}
        for reco_dir in reco_dirs:
            parts = [p for p in reco_dir.split("/") if p]
            if "pdata" not in parts:
                continue
            pdata_idx = parts.index("pdata")
            if pdata_idx < 1 or pdata_idx + 1 >= len(parts):
                continue

            scan_id_part = parts[pdata_idx - 1]
            if not scan_id_part.isdigit():
                continue
            scan_id = int(scan_id_part)

            reco_id_part = parts[pdata_idx + 1]
            if not reco_id_part.isdigit():
                continue

            scan_root = "/".join(parts[:pdata_idx])
            study_root = "/".join(parts[:pdata_idx - 1])
            
            if not (
                fs.exists(f"{scan_root}/method")
                and fs.exists(f"{scan_root}/acqp")
                and fs.exists(f"{reco_dir}/reco")
            ):
                continue

            study = studies.get(study_root)
            if study is None:
                study = cls(fs=fs, relroot=study_root, scans={})
                studies[study_root] = study

            if scan_id not in study.scans:
                study.scans[scan_id] = Scan.from_fs(fs, scan_id, scan_root)

        return [studies[k] for k in sorted(studies.keys())]

    @property
    def avail(self) -> Mapping[int, Union[Scan, "ScanLoader"]]:
        return {k: self.scans[k] for k in sorted(self.scans)}

    def get_scan(self, scan_id: int) -> Scan:
        return self.scans[scan_id]

    @property
    def has_subject(self) -> bool:
        target = f"{self.relroot}/subject" if self.relroot else "subject"
        return self.fs.exists(target)

    def __repr__(self) -> str:
        root_label = self.relroot or self.fs.root.name
        mode = getattr(self.fs, "_mode", "dir")

        subject_part = ""
        try:
            subj = getattr(self, "subject")
            from ..core.parameters import Parameters  # local import to avoid cycle

            if isinstance(subj, Parameters):
                sid = getattr(subj, "SUBJECT_id", None)
                name = getattr(subj, "SUBJECT_name_string", None)
                study_name = getattr(subj, "SUBJECT_study_name", None)
                study_nr = getattr(subj, "SUBJECT_study_nr", None)
                bits = []
                if name is not None:
                    bits.append(f"name={name!r}")
                if sid is not None:
                    bits.append(f"id={sid}")
                if study_name is not None:
                    bits.append(f"study={study_name!r}")
                if study_nr is not None:
                    bits.append(f"nr={study_nr}")
                if bits:
                    subject_part = " subject(" + " ".join(bits) + ")"
        except Exception:
            subject_part = ""

        return f"Study(root='{root_label}' mode={mode}{subject_part})"
