# Release v0.6.0a1

Date: 2026-09-26
Changes since 0.5.7

This is the first alpha of 0.6.0. It is a pre-release: it is tagged on the
development fork only and is not published to PyPI or TestPyPI.

The main goal of 0.6.0, a reworked context mapping for BIDS compatibility, is
**planned for 0.6.0b1** and is not in this alpha.

## Compatibility: outputs that change from 0.5.7

If you compare files written by 0.6.0a1 with files written by 0.5.7, you can
see the differences below. They are fixes, not regressions, but results made
with 0.5.7 for these cases do not match results made with 0.6.0a1.

### Subject orientation (affine)

0.6.0a1 rebuilds the subject orientation for all 16 subject poses
(Head/Foot x Supine/Prone/Left/Right) from one list of steps. The step back to
scanner space is now the exact reverse of the step into subject space.

- **Default output, `get_affine(space="subject_ras")`: 8 poses change.**
  - Biped: Head_Left, Head_Right.
  - Quadruped: Head_Supine, Foot_Supine, Head_Left, Head_Right, Foot_Left,
    Foot_Right.
  - Biped Foot_Left and Foot_Right do not change. In 0.5.7 two errors
    cancelled out for these two poses, so their result was already right.
- **Scanner space, `get_affine(space="scanner")`: 4 poses change.**
  Foot_Left and Foot_Right, for both Biped and Quadruped.
- **Pose or subject-type override** (`override_subject_pose` /
  `override_subject_type`, which go through `wrap_to_subject_ras`): 12 poses
  change, that is every Left/Right pose plus Quadruped Head_Supine and
  Foot_Supine.
- A missing subject type is still treated as Biped. Phantom, Other and
  OtherAnimal do not change.
- Function names, arguments and return types are unchanged.

What to do: if you have NIfTI files made with 0.5.7 from scans in one of the
poses above, convert them again with 0.6.0a1 before comparing or combining
them with new files.

### Scans whose slope or intercept differs per slice

ParaVision scaling (slope and intercept) can hold a different value per slice.
A NIfTI-1 header can hold only one slope and one intercept.

- **Before (0.5.7):** only one value went into the header, so voxel values
  were wrong for slices whose scaling differed from it.
- **Now (0.6.0a1):** when the values differ, BrkRaw applies them to the voxel
  data itself and sets the header scaling to slope 1, intercept 0. When all
  values are the same, the single value stays in the header as before.
- Effect: for such scans the stored voxel values and the data type of the
  output change (the data are stored already scaled, as floating point).
  Scans with one scaling value for the whole image are unchanged.
- When scaling is applied to the data (`dataobj` mode), the header scaling
  is now always reset to slope 1, intercept 0, so the scaling is not applied
  twice.

### Command line

- `brkraw -h` lists commands in groups by task. Only the help text layout
  changes; command names and plugin commands stay the same.
- `brkraw convert -h` groups its options by task. Option names, short aliases
  and environment variable fallbacks are meant to stay the same.
- Hook arguments given on the command line can now be lists or tuples.

## Other changes

- Development environment: uv with a tracked `uv.lock` and Python 3.12 for
  local work. Packaging and supported Python versions are unchanged.
- More tests for orientation steps and core extension contracts.
- Documentation: viewer extension boundaries; a warning on the context-map
  page (context mapping is still experimental).

## All commits since 0.5.7

### Orientation

- Test each orientation step through _apply_pose_step (7e82630)
- Rebuild subject orientation for all 16 poses from one labeled step list (54af07d)
- Fix quadruped supine subject affine (831b32a)

### Scaling and NIfTI

- Route loader scaling through NIfTI update (2d93b67)
- Model resolver scaling as array-capable metadata (63248f0)
- Handle nonuniform NIfTI scaling outside headers (1795e82)

### CLI

- Group CLI help output by workflow category (79dc2cc)
- Organize convert options by workflow (7d49e5f)
- Parse list/tuple hook args from CLI (1bedefb)

### Development and docs

- Manage the development environment with uv (tracked uv.lock, Python 3.12) (8479318)
- chore: ignore local agent guidance files (aa088b7)
- test: cover core extension contracts (f7dd331)
- docs: clarify viewer extension boundaries (ca58782)
- Add warning to context-map doc (2689553)
- ci: disabled automatic zenodo badge repleacing (69b393b)
- Update Zenodo DOI badge (f35a537)
