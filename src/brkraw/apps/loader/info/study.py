from __future__ import annotations

"""Resolve study-level metadata using remapping rules.

This module maps Paravision JCAMP parameters into a normalized dictionary.
It prefers subject-level parameters when available, and falls back to scan-level
visu_pars data when subject metadata is missing. Scan fallback selects the
first scan that contains a reco with a readable visu_pars object.
"""

from typing import Any, cast, TYPE_CHECKING, Dict, Optional
from pathlib import Path
from ....core.parameters import Parameters
from ....specs.remapper import load_spec, map_parameters
from ....specs.remapper.validator import validate_spec


if TYPE_CHECKING:
    from .. import BrukerLoader
    from ..types import StudyLoader


def resolve(loader: "BrukerLoader") -> Dict[str, Any]:
    """Resolve study/subject metadata into a normalized mapping.

    Args:
        loader: BrukerLoader instance providing access to Study/Scan/Reco nodes.

    Returns:
        A dictionary containing study and subject metadata fields.

    Raises:
        ValueError: If no scans are available or no scan has a readable
            visu_pars when subject metadata is missing.
    """
    def _resolve_section_transforms_path(section: Dict[str, Any]) -> Optional[Path]:
        meta = section.get("__meta__")
        if not isinstance(meta, dict) or not meta.get("transforms_source"):
            return None
        path = Path(meta["transforms_source"])
        if not path.is_absolute():
            path = (spec_path.parent / path).resolve()
        return path

    spec_path = Path(__file__).with_name("study.yaml")
    spec, transforms = load_spec(
        spec_path,
        validate=False,
    )
    validate_spec(spec["study"], transforms_source=_resolve_section_transforms_path(spec["study"]))
    validate_spec(spec["scan"], transforms_source=_resolve_section_transforms_path(spec["scan"]))
    study = cast("StudyLoader", loader._study)
    if study.has_subject:
        return map_parameters(study, spec["study"], transforms=transforms, validate=True)
    else:
        if not study.avail:
            raise ValueError("No scans available to resolve study info from visu_pars.")
        scan_with_visu = None
        for scan in study.avail.values():
            for reco in scan.avail.values():
                visu = getattr(reco, "visu_pars", None)
                if isinstance(visu, Parameters):
                    scan_with_visu = scan
                    break
            if scan_with_visu is not None:
                break
        if scan_with_visu is None:
            raise ValueError("No scan contains a reco with readable visu_pars for study info.")
        return map_parameters(scan_with_visu, spec["scan"], transforms=transforms)
