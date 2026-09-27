"""Per-frame VisuCoreDataSlope (BRK-0035, option C). Synthetic data only.

ParaVision stores one slope value per frame (a 2D slice or a 3D volume) in
2dseq frame order. Equal values become one header scalar and the data stays
raw (as 0.5.7); different values are applied to the data frame by frame
(float data, header slope 1), before slice packs are split and frames are
selected, so every output keeps the right value for its frames.
"""
from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

import brkraw
from brkraw.cli.main import main

from tests.helpers import make_synthetic_study


def _raw(study: Path, scan_id: int):
    return brkraw.load(str(study)).get_dataobj(scan_id, 1)


def _convert(study: Path, scan_id: int, out: Path, *extra: str) -> nib.Nifti1Image:
    assert main(["convert", str(study), "-s", str(scan_id), "-o", str(out), "--no-context-map", *extra]) == 0
    return nib.load(str(out))


def _values(img: nib.Nifti1Image) -> np.ndarray:
    # values after the header scaling
    return np.asarray(img.get_fdata())


def test_equal_per_frame_slope_stays_in_the_header(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [2.0, 2.0, 2.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz")
    raw = np.asarray(_raw(st, 5))
    assert img.get_data_dtype() == np.dtype("int16")
    assert np.array_equal(np.asarray(img.dataobj.get_unscaled()), raw)
    assert img.header.get_slope_inter() == (2.0, 0.0)
    assert np.allclose(_values(img), raw * 2.0)


def test_different_per_frame_slopes_are_applied_per_frame(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz")
    raw = np.asarray(_raw(st, 5), dtype=float)
    assert np.allclose(_values(img), raw * np.array([1.0, 2.0, 3.0]))
    assert img.header.get_slope_inter()[0] in (None, 1.0)


def test_per_frame_slopes_follow_slice_packs(tmp_path):
    # frames in 2dseq order: slice (= pack) fastest, then cycle; frame = pack + 2 * cycle
    slopes = [1.0, 10.0, 2.0, 20.0, 3.0, 30.0]
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={7: "EPI"},
                              frames={7: [("FG_CYCLE", 3)]}, packs={7: 2}, slopes={7: slopes})
    out = tmp_path / "o"
    assert main(["convert", str(st), "-s", "7", "-o", str(out) + "/", "--no-context-map"]) == 0
    packs = _raw(st, 7)
    files = sorted(out.glob("*.nii.gz"))
    assert len(files) == 2
    for p, path in enumerate(files):
        expected = np.asarray(packs[p], dtype=float) * np.array([slopes[p + 2 * c] for c in range(3)])
        assert np.allclose(_values(nib.load(str(path))), expected)


def test_per_frame_slopes_follow_the_frame_order_when_slice_is_not_first(tmp_path):
    # FG order echo, slice: frame = echo + 2 * slice
    slopes = [1.0, 2.0, 10.0, 20.0]
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "FieldMap"},
                              frames={9: [("FG_ECHO", 2), ("FG_SLICE", 2)]}, packs={9: 2}, slopes={9: slopes})
    out = tmp_path / "o"
    assert main(["convert", str(st), "-s", "9", "-o", str(out) + "/", "--no-context-map"]) == 0
    packs = _raw(st, 9)
    files = sorted(out.glob("*.nii.gz"))
    assert len(files) == 2
    for p, path in enumerate(files):
        expected = np.asarray(packs[p], dtype=float) * np.array([slopes[e + 2 * p] for e in range(2)])
        assert np.allclose(_values(nib.load(str(path))), expected)


@pytest.mark.parametrize(
    "extra, index, scale",
    [
        (["--axis", "cycle", "--frames", "2"], (Ellipsis, 2), 3.0),
        (["--frames", "2,0"], (Ellipsis, [2, 0]), np.array([3.0, 1.0])),
        (["--frames", "1:3"], (Ellipsis, slice(1, 3)), np.array([2.0, 3.0])),
        (["--cycle-index", "1", "--cycle-count", "2"], (Ellipsis, slice(1, 3)), np.array([2.0, 3.0])),
    ],
)
def test_frame_selection_keeps_each_frames_slope(tmp_path, extra, index, scale):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    img = _convert(st, 5, tmp_path / "o.nii.gz", *extra)
    raw = np.asarray(_raw(st, 5), dtype=float)
    assert np.allclose(_values(img), raw[index] * scale)


def test_split_parts_keep_each_frames_slope(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={8: "FieldMap"},
                              frames={8: [("FG_ECHO", 2)]}, slopes={8: [1.0, 5.0]})
    (st.parent / f"{st.name}.yaml").write_text(yaml.safe_dump({
        "__meta__": {"category": "context_map", "layout_template": "E{x.scan}_part{utils.split}"},
        "x": {"scan": {"from": "ScanID"}},
        "split": [{"axis": "echo", "frames": 0}, {"axis": "echo", "frames": 1}],
    }), encoding="utf-8")
    out = tmp_path / "o"
    assert main(["convert", str(st), "-o", str(out)]) == 0
    raw = np.asarray(_raw(st, 8), dtype=float)
    assert np.allclose(_values(nib.load(str(out / "E8_part1.nii.gz"))), raw[..., 0] * 1.0)
    assert np.allclose(_values(nib.load(str(out / "E8_part2.nii.gz"))), raw[..., 1] * 5.0)


def test_flatten_after_per_frame_scaling(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={9: "EPI"},
                              frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 2)]}, slopes={9: [1.0, 2.0, 3.0, 4.0]})
    img = _convert(st, 9, tmp_path / "o.nii.gz", "-F")
    raw = np.asarray(_raw(st, 9), dtype=float)  # (4, 4, 1, 2, 2): echo fastest
    scaled = raw * np.array([[1.0, 3.0], [2.0, 4.0]])  # [echo, cycle] -> frame echo + 2 * cycle
    assert np.allclose(_values(img), scaled.reshape((4, 4, 1, 4), order="A"))


def test_get_dataobj_stays_raw_with_per_frame_slopes(tmp_path):
    st = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                              frames={5: [("FG_CYCLE", 3)]}, slopes={5: [1.0, 2.0, 3.0]})
    data = np.asarray(_raw(st, 5))
    assert data.dtype == np.int16
    assert np.array_equal(data.reshape(-1, order="F"), np.arange(48))
