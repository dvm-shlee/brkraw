"""Internal helper functions for BrukerLoader.

Last updated: 2025-12-30
"""

from __future__ import annotations

from types import MethodType
from typing import TYPE_CHECKING, Optional, Tuple, Union, Any, Mapping, cast, List, Dict
from pathlib import Path
from warnings import warn

import numpy as np
from nibabel.nifti1 import Nifti1Image

from ...core.config import resolve_root
from ...core.parameters import Parameters
from ...specs.remapper import load_spec, map_parameters
from ...specs.rules import load_rules, select_rule_use
from ...dataclasses import Reco, Scan, Study
from .types import StudyLoader, ScanLoader
from ...specs import converter as converter_core
from ...resolver import affine as affine_resolver
from ...resolver import image as image_resolver
from ...resolver import fid as fid_resolver
from ...resolver import nifti as nifti_resolver
from ...resolver.helpers import get_file

if TYPE_CHECKING:
    from ...resolver.nifti import Nifti1HeaderContents
    from .types import SubjectType, SubjectPose, XYZUNIT, TUNIT


def make_dir(names: List[str]):
    """Return a stable __dir__ function for a module."""
    def _dir() -> List[str]:
        return sorted(names)
    return _dir


def _resolve_data_and_affine(
    scan: Union["Scan", "ScanLoader"],
    reco_id: int = 1,
    *,
    affine_decimals: int = 6,
):
    """Populate per-reco image/affine resolver outputs on a scan.

    Args:
        scan: Scan node to attach image/affine info.
        reco_id: Reco identifier to resolve (default: 1).
        affine_decimals: Decimal rounding applied to resolved affines.
    """
    scan = cast(ScanLoader, scan)

    image_info = image_resolver.resolve(scan, reco_id)
    # force unwrap pose to scanner's view
    affine_info = affine_resolver.resolve(
        scan, reco_id, decimals=affine_decimals, unwrap_pose=True
    )

    if hasattr(scan, "image_info"):
        scan.image_info[reco_id] = image_info
    else:
        setattr(scan, "image_info", {reco_id: image_info})
    if hasattr(scan, "affine_info"):
        scan.affine_info[reco_id] = affine_info
    else:
        setattr(scan, "affine_info", {reco_id: affine_info})
    scan.get_fid = MethodType(fid_resolver.resolve, scan)


def _search_parameters(
    self: Union[Study, Scan, Reco],
    key: str,
    file: Optional[Union[str, List[str]]] = None,
    scan_id: Optional[int] = None,
    reco_id: Optional[int] = None,
) -> Optional[dict]:
    """Search parameter files for keys on Study/Scan/Reco objects.

    Results are grouped by filename. When searching a Study/Scan without
    reco_id, scan and reco hits are merged as
    `{filename: {"scan": {...}, "reco_<id>": {...}}}`. With a specific reco_id
    (or Reco), results stay flat as `{filename: {matched_key: value}}`.
    Missing files are ignored; non-parameter files raise TypeError.

    Args:
        self: Study, Scan, or Reco instance.
        key: Parameter key to search for.
        file: Filename or list of filenames to search (default: common set).
        scan_id: Scan id (required when searching from Study).
        reco_id: Reco id (optional; flattens results for that reco).

    Returns:
        Mapping of filename to found values, or None if no hits.
    """

    files = ["method", "acqp", "visu_pars", "reco"] if file is None else file
    files = [files] if isinstance(files, str) else list(files)

    def load_parameters(obj: Union[Study, Scan, Reco], filename: str) -> Optional[Parameters]:
        try:
            params = get_file(obj, filename)
        except FileNotFoundError:
            return None
        if not isinstance(params, Parameters):
            raise TypeError(f"Not a Paravision parameter file: {filename}")
        return params

    def flatten_matches(matches: List[dict]) -> dict:
        flat: dict = {}
        for entry in matches:
            flat.update(entry)
        return flat

    def search_node(node: Union[Study, Scan, Reco]) -> Dict[str, dict]:
        hits: Dict[str, dict] = {}
        for fname in files:
            params = load_parameters(node, fname)
            if params is None:
                continue
            matches = params.search_keys(key)
            if matches:
                hits[fname] = flatten_matches(matches)
        return hits

    def search_recos(scan_obj: Scan) -> Dict[int, Dict[str, dict]]:
        reco_hits: Dict[int, Dict[str, dict]] = {}
        for rid, reco in scan_obj.avail.items():
            hits = search_node(reco)
            if hits:
                reco_hits[rid] = hits
        return reco_hits

    def merge_scan_and_recos(
        scan_hits: Dict[str, dict], reco_hits: Dict[int, Dict[str, dict]]
    ) -> Dict[str, Union[Dict[str, dict], dict]]:
        """Merge scan/reco hits by filename.

        Args:
            scan_hits: Per-filename hits from the scan object.
            reco_hits: Per-reco hits keyed by reco id.

        Returns:
            Merged mapping keyed by filename.
        """
        if not scan_hits and not reco_hits:
            return {}

        merged: Dict[str, Union[Dict[str, dict], dict]] = {}
        all_fnames = set(scan_hits) | {fname for rh in reco_hits.values() for fname in rh}
        for fname in all_fnames:
            scan_hit = scan_hits.get(fname)
            reco_for_fname = {
                f"reco_{rid}": rhits[fname]
                for rid, rhits in reco_hits.items()
                if fname in rhits
            }
            if reco_for_fname:
                merged[fname] = {}
                if scan_hit:
                    merged[fname]["scan"] = scan_hit
                merged[fname].update(reco_for_fname)
            elif scan_hit:
                merged[fname] = scan_hit
        return merged

    if isinstance(self, Study):
        if scan_id is None:
            warn("To search from Study object, specifying <scan_id> is required.")
            return None
        scan = self.get_scan(scan_id)
        scan_hits = search_node(scan)
        if reco_id is None:
            reco_hits = search_recos(scan)
            merged = merge_scan_and_recos(scan_hits, reco_hits)
            return merged or None
        # specific reco: keep flat
        result: Dict[str, dict] = {}
        if scan_hits:
            result.update(scan_hits)
        reco = scan.get_reco(reco_id)
        reco_hits = search_node(reco)
        if reco_hits:
            result.update(reco_hits)
        return result or None

    if isinstance(self, Scan):
        scan_hits = search_node(self)
        if reco_id is None:
            reco_hits = search_recos(self)
            merged = merge_scan_and_recos(scan_hits, reco_hits)
            return merged or None
        # specific reco: keep flat
        result: Dict[str, dict] = {}
        if scan_hits:
            result.update(scan_hits)
        reco_hits = search_node(self.get_reco(reco_id))
        if reco_hits:
            result.update(reco_hits)
        return result or None

    if isinstance(self, Reco):
        reco_hits = search_node(self)
        return reco_hits or None

    return None


def _get_dataobj(
    self: Union["Scan", "ScanLoader"], reco_id: int = 1
) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]:
    """Return reconstructed data for a reco, split by slice pack if needed.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (default: 1).

    Returns:
        Single ndarray when one slice pack exists; otherwise a tuple of arrays.
        Returns None when required metadata is unavailable.
    """
    if not hasattr(self, "image_info") or not hasattr(self, "affine_info"):
        return None
    self = cast(ScanLoader, self)
    affine_info = self.affine_info.get(reco_id)
    image_info = self.image_info.get(reco_id)
    if affine_info is None or image_info is None:
        return None

    num_slices = affine_info["num_slices"]
    dataobj = image_info["dataobj"]

    slice_pack = []
    slice_offset = 0
    for _num_slices in num_slices:
        _dataobj = dataobj[:, :, slice(slice_offset, slice_offset + _num_slices)]
        slice_offset += _num_slices
        slice_pack.append(_dataobj)

    if len(slice_pack) == 1:
        return slice_pack[0]
    return tuple(slice_pack)


def _get_affine(
    self: Union["Scan", "ScanLoader"],
    reco_id: int = 1,
    *,
    unwrap_pose: bool = False,
    override_subject_type: Optional[SubjectType] = None,
    override_subject_pose: Optional[SubjectPose] = None,
) -> Optional[Union[Tuple["np.ndarray", ...], "np.ndarray"]]:
    """Return affine(s) for a reco, optionally in scanner view.

    When unwrap_pose=False (default), return subject-view affines aligned to
    RAS (subject space). When unwrap_pose=True, return scanner-view affines.
    Subject pose/type overrides apply only in subject view and are rejected
    when unwrap_pose=True.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (default: 1).
        unwrap_pose: If True, return scanner-view affines. If False, return
            subject-view affines aligned to RAS (default: False).
        override_subject_type: Subject type override used for subject-view
            pose wrapping. Ignored when unwrap_pose=True.
        override_subject_pose: Subject pose override used for subject-view
            pose wrapping. Ignored when unwrap_pose=True.

    Returns:
        Single affine matrix when one slice pack exists; otherwise a tuple of
        affines. Returns None when affine info is unavailable.

    Raises:
        ValueError: If override_subject_type/override_subject_pose is provided
            when unwrap_pose=True.
    """
    if not hasattr(self, "affine_info"):
        return None

    self = cast(ScanLoader, self)
    affine_info = self.affine_info.get(reco_id)
    if affine_info is None:
        return None
    num_slice_packs = affine_info["num_slice_packs"]
    affines = affine_info["affines"]

    if not unwrap_pose:
        visu_pars = get_file(self.avail[reco_id], "visu_pars")
        subj_type, subj_pose = affine_resolver.get_subject_type_and_position(visu_pars)
        override_subject_type = override_subject_type or subj_type
        override_subject_pose = override_subject_pose or subj_pose

        affines = [
            affine_resolver.wrap_subject_pose(
                affine, override_subject_type, override_subject_pose
            )
            for affine in affines
        ]
    else:
        if override_subject_pose is not None or override_subject_type is not None:
            raise ValueError(
                "override_subject_type/override_subject_pose cannot be used with "
                "unwrap_pose=True. Use either subject-view overrides or scanner-view "
                "unwrap, not both."
            )
    if num_slice_packs == 1:
        return affines[0]
    return tuple(affines)


def _get_nifti1image(
    self: Union["Scan", "ScanLoader"],
    reco_id: int = 1,
    *,
    unwrap_pose: bool = False,
    override_header: Optional[Nifti1HeaderContents] = None,
    override_subject_type: Optional[SubjectType] = None,
    override_subject_pose: Optional[SubjectPose] = None,
    flip_x: bool = False,
    xyz_units: XYZUNIT = "mm",
    t_units: TUNIT = "sec",
) -> Optional[Union[Tuple["Nifti1Image", ...], "Nifti1Image"]]:
    """Return NIfTI image(s) for a reco.

    Args:
        self: Scan or ScanLoader instance.
        reco_id: Reco identifier to read (default: 1).
        unwrap_pose: If True, use scanner-view affines. If False, use
            subject-view affines (default: False).
        override_header: Optional header values to apply.
        override_subject_type: Subject type override for subject-view wrapping.
        override_subject_pose: Subject pose override for subject-view wrapping.
        flip_x: If True, set NIfTI header x-flip flag.
        xyz_units: Spatial units for NIfTI header.
        t_units: Temporal units for NIfTI header.

    Returns:
        Single NIfTI image when one slice pack exists; otherwise a tuple of
        images. Returns None when required metadata is unavailable.
    """

    if not all(
        hasattr(self, attr) for attr in ["image_info", "affine_info", "get_dataobj", "get_affine"]
    ):
        return None

    self = cast(ScanLoader, self)
    dataobjs = self.get_dataobj(reco_id)
    affines = self.get_affine(
        reco_id,
        unwrap_pose=unwrap_pose,
        override_subject_type=override_subject_type,
        override_subject_pose=override_subject_pose,
    )
    image_info = self.image_info.get(reco_id)

    if dataobjs is None or affines is None or image_info is None:
        return None

    if not isinstance(dataobjs, tuple) and not isinstance(affines, tuple):
        dataobjs = (dataobjs,)
        affines = (affines,)

    niiobjs = []
    for i, dataobj in enumerate(dataobjs):
        affine = affines[i]
        niiobj = Nifti1Image(dataobj, affine)
        nifti1header_contents = nifti_resolver.resolve(
            image_info, flip_x=flip_x, xyz_units=xyz_units, t_units=t_units
        )
        if override_header:
            for key, value in override_header.items():
                if value is not None:
                    nifti1header_contents[key] = value
        niiobj = nifti_resolver.update(niiobj, nifti1header_contents)
        niiobjs.append(niiobj)

    if len(niiobjs) == 1:
        return niiobjs[0]
    return tuple(niiobjs)


def _resolve_metadata_spec(
    scan: "ScanLoader",
    spec: Optional[Union[Mapping[str, Any], str, Path]],
    *,
    base: Path,
) -> Optional[Tuple[Mapping[str, Any], Dict[str, Any], Optional[Path]]]:
    """Resolve a metadata spec and its transforms for a scan.

    Args:
        scan: Scan instance to evaluate rules against.
        spec: Optional spec mapping or spec path override.
        base: Config root directory for rule resolution.

    Returns:
        Tuple of (spec, transforms, spec_path) or None when no spec matches.
    """
    if spec is None:
        try:
            rules = load_rules(root=base, validate=False)
        except Exception:
            return None
        spec_path = select_rule_use(
            scan,
            rules.get("metadata_spec", []),
            base=base,
            resolve_paths=True,
        )
        if not isinstance(spec_path, Path) or not spec_path.exists():
            return None
        spec_data, transforms = load_spec(spec_path, validate=False)
        return spec_data, transforms, spec_path
    if isinstance(spec, (str, Path)):
        spec_path = Path(spec)
        spec_data, transforms = load_spec(spec_path, validate=False)
        return spec_data, transforms, spec_path
    if isinstance(spec, Mapping):
        return spec, {}, None
    raise TypeError(f"Unsupported spec type: {type(spec)!r}")


def _get_metadata(
    self,
    reco_id: int = 1,
    spec: Optional[Union[Mapping[str, Any], str, Path]] = None,
    return_spec: bool = False,
):
    """Resolve metadata using a remapper spec.

    Args:
        self: Scan instance.
        reco_id: Reco identifier (default: 1).
        spec: Optional spec mapping or spec file path.
        return_spec: If True, return spec info alongside metadata.

    Returns:
        Mapping of metadata fields, or None when no spec matches. When
        return_spec is True, returns (metadata, spec_info).
    """
    scan = cast(ScanLoader, self)
    base = resolve_root(None)
    resolved = _resolve_metadata_spec(scan, spec, base=base)
    if resolved is None:
        if return_spec:
            return None, None
        return None
    spec_data, transforms, spec_path = resolved
    metadata = map_parameters(scan, spec_data, transforms, validate=False)
    if not return_spec:
        return metadata
    meta = spec_data.get("__meta__")
    name = meta.get("name") if isinstance(meta, dict) else None
    spec_info = {"path": spec_path, "name": name}
    return metadata, spec_info


def _apply_converter_entrypoint(
    scan: "ScanLoader",
    converter_entrypoint: Mapping[str, Any],
) -> None:
    """Override scan conversion helpers using a converter entrypoint."""
    converter_core.validate_entrypoint(converter_entrypoint)
    plugin = dict(converter_entrypoint)
    scan._converter_entrypoint = plugin
    if "get_dataobj" in plugin:
        scan.get_dataobj = MethodType(plugin["get_dataobj"], scan)
    if "get_affine" in plugin:
        scan.get_affine = MethodType(plugin["get_affine"], scan)
    if "get_nifti1image" in plugin:
        scan.get_nifti1image = MethodType(plugin["get_nifti1image"], scan)
