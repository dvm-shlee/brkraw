"""0.6.0rc2 hook API (BRK-0046): a converter hook's `convert` gets the reco id,
and hooks can apply brkraw's per-frame slope/offset rule (BRK-0036) through
the public `scale_frames`. Synthetic data only."""
from __future__ import annotations

import numpy as np
import pytest

import brkraw
from brkraw.apps.loader import helper

from tests.helpers import make_synthetic_study


def _study(tmp_path, slopes):
    return make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={5: "EPI"},
                                frames={5: [("FG_CYCLE", 3)]}, slopes={5: slopes})


def _bind(loader, scan_id, hook):
    scan = loader.get_scan(scan_id)
    helper.apply_converter_hook(scan, hook)
    return scan


# ---------------------------------------------------------------------------
# reco_id reaches the hook's convert
# ---------------------------------------------------------------------------


def test_hook_with_kwargs_gets_reco_id(tmp_path):
    seen = {}

    def convert(scan, dataobj, affine, **kwargs):
        seen.update(kwargs)
        return None

    loader = brkraw.load(str(_study(tmp_path, [1.0, 1.0, 1.0])))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1)
    assert seen.get("reco_id") == 1


def test_hook_convert_gets_the_frame_selection_and_can_scale_it(tmp_path):
    got = {}

    def convert(scan, dataobj, affine, **kwargs):
        got.update(kwargs)
        data = dataobj if isinstance(dataobj, tuple) else (dataobj,)
        got["scaled"], got["applied"] = helper.scale_frames(
            scan, kwargs["reco_id"], data, axis=kwargs.get("axis"), frames=kwargs.get("frames"))
        return None

    st = _study(tmp_path, [1.0, 2.0, 3.0])
    loader = brkraw.load(str(st))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1, axis="cycle", frames=[0, 2])
    assert got["axis"] == "cycle" and got["frames"] == [0, 2]
    ref = brkraw.load(str(st)).convert(5, reco_id=1, axis="cycle", frames=[0, 2])
    assert got["applied"] is True
    assert np.allclose(got["scaled"][0], np.asarray(ref.dataobj))


def test_hook_with_a_reco_id_parameter_gets_it(tmp_path):
    seen = []

    def convert(scan, dataobj, affine, reco_id=None):
        seen.append(reco_id)
        return None

    loader = brkraw.load(str(_study(tmp_path, [1.0, 1.0, 1.0])))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1)
    assert seen == [1]


def test_hook_without_it_is_called_as_before(tmp_path):
    calls = []

    def convert(scan, dataobj, affine):
        calls.append(True)
        return None

    loader = brkraw.load(str(_study(tmp_path, [1.0, 1.0, 1.0])))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1)
    assert calls == [True]


def test_hook_still_gets_raw_data(tmp_path):
    got = {}

    def convert(scan, dataobj, affine, **kwargs):
        got["data"] = dataobj
        return None

    st = _study(tmp_path, [1.0, 2.0, 3.0])
    raw = np.asarray(brkraw.load(str(st)).get_dataobj(5, 1))
    loader = brkraw.load(str(st))
    _bind(loader, 5, {"convert": convert})
    loader.convert(5, reco_id=1)
    data = got["data"][0] if isinstance(got["data"], tuple) else got["data"]
    assert np.array_equal(np.asarray(data), raw)


# ---------------------------------------------------------------------------
# scale_frames: the same rule as convert(), for hooks
# ---------------------------------------------------------------------------


def test_scale_frames_is_public():
    from brkraw import api

    assert callable(helper.scale_frames)
    assert api.scale_frames is helper.scale_frames
    assert "scale_frames" in api.__all__


def test_scale_frames_applies_different_per_frame_slopes(tmp_path):
    st = _study(tmp_path, [1.0, 2.0, 3.0])
    loader = brkraw.load(str(st))
    scan = loader.get_scan(5)
    raw = scan.get_dataobj(1)
    scaled, applied = helper.scale_frames(scan, 1, (raw,))
    assert applied is True
    assert np.allclose(scaled[0], np.asarray(raw, dtype=float) * np.array([1.0, 2.0, 3.0]))
    # same values as the default convert()
    ref = brkraw.load(str(st)).convert(5, reco_id=1)
    assert np.allclose(scaled[0], np.asarray(ref.dataobj))


def test_scale_frames_leaves_equal_slopes_to_the_header(tmp_path):
    st = _study(tmp_path, [2.0, 2.0, 2.0])
    scan = brkraw.load(str(st)).get_scan(5)
    raw = scan.get_dataobj(1)
    scaled, applied = helper.scale_frames(scan, 1, (raw,))
    assert applied is False
    assert scaled[0] is raw


def test_scale_frames_output_goes_through_get_nifti1image(tmp_path):
    st = _study(tmp_path, [1.0, 2.0, 3.0])
    scan = brkraw.load(str(st)).get_scan(5)
    raw = scan.get_dataobj(1)
    affine = scan.get_affine(1)
    scaled, applied = helper.scale_frames(scan, 1, (raw,))
    img = scan.get_nifti1image(reco_id=1, dataobjs=scaled,
                               affines=affine if isinstance(affine, tuple) else (affine,),
                               scaling_applied=applied)
    img = img[0] if isinstance(img, tuple) else img
    assert img.header.get_slope_inter()[0] in (None, 1.0)
    assert np.allclose(np.asarray(img.dataobj), np.asarray(raw, dtype=float) * np.array([1.0, 2.0, 3.0]))


# ---------------------------------------------------------------------------
# wi-0038-choi-3: legacy cycle selection and -F (flatten_fg) for hooks
# ---------------------------------------------------------------------------


def _scaling_hook(got):
    def convert(scan, dataobj, affine, **kwargs):
        got.update(kwargs)
        data = dataobj if isinstance(dataobj, tuple) else (dataobj,)
        got["scaled"], got["applied"] = helper.scale_frames(
            scan, kwargs["reco_id"], data,
            **{k: kwargs.get(k) for k in ("axis", "frames", "cycle_index", "cycle_count")})
        return None
    return convert


def test_hook_convert_gets_the_legacy_cycle_selection_and_can_scale_it(tmp_path):
    got = {}
    st = _study(tmp_path, [1.0, 2.0, 3.0])
    loader = brkraw.load(str(st))
    _bind(loader, 5, {"convert": _scaling_hook(got)})
    loader.convert(5, reco_id=1, cycle_index=1, cycle_count=2)
    assert got["cycle_index"] == 1 and got["cycle_count"] == 2
    ref = brkraw.load(str(st)).convert(5, reco_id=1, cycle_index=1, cycle_count=2)
    assert got["applied"] is True
    assert np.allclose(got["scaled"][0], np.asarray(ref.dataobj))


def _study_2fg(tmp_path):
    # 2 echoes x 3 cycles, a different slope for each of the 6 frames
    return make_synthetic_study(tmp_path / "s2", pv="360.3.3", scans={9: "MGE"},
                                frames={9: [("FG_ECHO", 2), ("FG_CYCLE", 3)]},
                                slopes={9: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})


@pytest.mark.parametrize("selection", [{}, {"axis": "cycle", "frames": [0, 2]}])
def test_scale_frames_accepts_data_flattened_by_flatten_fg(tmp_path, selection):
    # brkraw flattens frame axes above 4D (-F) before a hook gets the data;
    # scale_frames must scale those data like the default path (scale, then flatten)
    got = {}
    st = _study_2fg(tmp_path)
    loader = brkraw.load(str(st))
    _bind(loader, 9, {"convert": _scaling_hook(got)})
    loader.convert(9, reco_id=1, flatten_fg=True, **selection)
    ref = brkraw.load(str(st)).convert(9, reco_id=1, flatten_fg=True, **selection)
    expected = np.asarray(ref.dataobj)
    assert expected.ndim == 4
    assert got["applied"] is True
    assert got["scaled"][0].shape == expected.shape
    assert np.allclose(got["scaled"][0], expected)


def test_get_nifti1image_without_scaling_still_refuses_per_frame_slopes(tmp_path):
    scan = brkraw.load(str(_study(tmp_path, [1.0, 2.0, 3.0]))).get_scan(5)
    raw = scan.get_dataobj(1)
    affine = scan.get_affine(1)
    with pytest.raises(ValueError, match="scale_frames"):
        scan.get_nifti1image(reco_id=1, dataobjs=(raw,),
                             affines=affine if isinstance(affine, tuple) else (affine,))
