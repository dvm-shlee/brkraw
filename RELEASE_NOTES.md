# Release v0.6.0b1

Date: 2026-09-27
Changes since 0.6.0a1 (and 0.5.7)

This is the first beta of 0.6.0. It is a pre-release: it is tagged on the
development fork only and is not published to PyPI or TestPyPI. Names and
options may still change before 0.6.0rc1 based on feedback.

The main goal of 0.6.0, context mapping for BIDS-style output, is in this
beta. **Moving from 0.5.x or 0.6.0a1: read
[Migrating to 0.6](docs/getting-started/migrating.md)** (the same page is in
the documentation).

## Highlights

- **Context maps v3.** A YAML file next to a dataset (same name) defines output
  values in namespaces you name, without changing the original information.
  Four value forms (direct, `from`, `from` + `map` + `default`, `when`), a
  `layout_template` with optional `[ ... ]` groups and `utils` values
  (`counter`, `slicepack`, `split`), `convert: false` to skip scans, `split`
  of multi-frame scans with numpy-style `{axis, frames}`, `sidecar` fields,
  and `include` of shared base maps. Output paths are planned first; a name
  collision stops the run by default (`on_collision: suffix` adds `_2`, `_3`).
- **`MethodBase`**: the method without the vendor prefix (`Bruker:EPI` →
  `EPI`); `Method` keeps the original value.
- **Frame selection**: `brkraw convert --axis/--frames` and
  `get_dataobj(..., axis=, frames=)`; `brkraw info` shows each reco's frame
  axes. `--cycle-index/--cycle-count` (and `cycle_index/cycle_count`) still
  work with a deprecation warning and are removed in 0.7.0.
- **prune redesign**: without a spec, the chosen scans are copied unchanged
  into `pruned_<study>.zip`; `--anonymize` applies the example spec
  `anonymize`; `--files`, `--exclude-files`, `--institution`, `--dry-run`;
  safe writing (temporary file, no overwrite without `--overwrite`, ZIP64 for
  large members); a `.prune.yaml` record with names only. Pruner spec keys
  `jcamp_headers` and `anonymize: true`.
- **CLI**: `convert --batch` (replaces `convert-batch`), `brkraw init` only
  (`config init` removed), `--root` on every command, a ParaVision study
  chooser on scanner consoles.
- **Shared context maps**: `brkraw addon add` installs a base map into the new
  config folder `context_maps/`; hook packages can ship base maps (manifest
  key `context_maps`).

## Compatibility: what changes

0.6.0 changes names and syntax directly, without aliases (except the cycle
options above).

| Removed or renamed | Use instead |
| --- | --- |
| context map syntax of 0.5.x (`type: mapping`, `cases`, `selector`, `target`, `override`, `__split__`, `__meta__.layout_entries`, `__meta__.slicepack_suffix`) | context map v3 (the loader names the old word) |
| `BRKRAW_CONVERT_CONTEXT_MAP`, `session set --convert-option CONTEXT_MAP=…` | same-name file next to the dataset, or `-M FILE` |
| `brkraw convert-batch` | `brkraw convert --batch` |
| `brkraw config init` | `brkraw init` |
| `brkraw prune --spec-name`, `--scan-ids`, `--reco-ids`, `--mode` | `--spec`, `-s/--scan-id`, `-r/--reco-id`, `--files` / `--exclude-files` |
| built-in pruner spec `deid4share` | `anonymize` (`--anonymize`) |
| `from brkraw.api import addon` (context maps) | `from brkraw.api import context_map` |
| `src/brkraw/schema/context_map.yaml` | removed (validation is in `brkraw.specs.context_map`) |

Behavior to know:

- `brkraw prune DATA` without a spec no longer stops; it copies without
  changing values. Nothing is anonymized unless you ask.
- `brkraw init --yes` writes `config.yaml` with defaults **and appends the
  shell helpers to `~/.zshrc` or `~/.bashrc`** when your shell is zsh or bash
  (also with `--install-default`). A quieter option is planned.

## Outputs that change

### Intensity scaling (slope and offset)

ParaVision stores one `VisuCoreDataSlope` / `VisuCoreDataOffs` value per frame.

- **0.6.0a1 stopped** with "VisuCoreDataSlope has N values" on every reco with
  more than one frame per slice (multi-echo, DTI, repeated scans, multi-frame
  3D). **Fixed in this beta**; do not use 0.6.0a1 for such data.
- Exactly equal values stay one header value and the data keeps its integer
  type: the output equals 0.5.7.
- Different values are applied to their own frames (the count is matched
  against the slice packs first, then against the frame axes multiplied from
  the last one); the data is written as floating point with header slope 1,
  so **such files are larger**. When no layout matches, brkraw warns and
  writes the data without scaling.
- Compared with 0.5.7 on brkraw's test data (61 datasets, 582 recos): 536
  exactly equal, 11 different — all with slopes that differ per frame: 10 DTI
  images (reco 2; slopes differing by factors from 10³ to about 10⁹) and one
  functional (fMRI) time series whose slope differs per repetition (up to
  about **3 %** over time). 0.5.7 scaled these with the first frame's value
  only. In the same data, 547 recos convert in both versions and 0.6.0b1 fails
  none that 0.5.7 converts; every converted reco matches an independent
  numpy reference (24 exactly, 523 within 1e-6).
- New warnings (data unchanged): the frames of one slice pack do not share one
  orientation; the slice packs do not add up to the slice frame group; a slope
  or offset stored with 2+ dimensions does not match the frame axes. None
  appeared on the 107 multi-pack recos checked.

### Subject orientation (from 0.6.0a1, unchanged)

The subject orientation of all 16 poses is rebuilt from one list of steps.
Default output (`subject_ras`): 8 poses change from 0.5.7 (Biped Head_Left,
Head_Right; Quadruped Head_Supine, Foot_Supine, Head_Left, Head_Right,
Foot_Left, Foot_Right). Scanner space: 4 poses (Foot_Left, Foot_Right for Biped
and Quadruped). With a pose or subject-type override: 12 poses. Convert again
before comparing or combining with 0.5.7 outputs.

## Other changes

- Tests: config isolation for every test, a synthetic PvDataset builder,
  optional tests on approved anonymized studies kept outside the repository
  (`BRKRAW_AGENT_FIXTURES`), the documentation's BIDS example checked by the
  test suite; a documentation build check (`mkdocs build --strict`) in CI;
  MkDocs pinned below 2 in the workflows.
- `unixtime_to_datetime` and study info tolerate missing dates (anonymized
  data loads).
- `brkraw.api.layout` is public; `brkraw config path` knows `pruner_specs` and
  `context_maps`.
- Documentation: rewritten context map, BIDS, prune, convert and layout pages;
  new "Pruner specs" and "Migrating to 0.6"; navigation by the CLI groups;
  consistent terms.

## All commits since 0.6.0a1

### Test base

- Add failing tests for the shared test base (376146d)
- Isolate tests from local settings; add agent-fixture lookup, synthetic PvDataset builder and docs build check (4d3ee58)

### prune

- Add failing tests for prune fixes 1-5 and safe writing (1edd835)
- Fix prune defects 1-5 and write zips safely (7e5f2ad)
- Add failing tests for the prune 0.6.0 design (8ffffe3)
- prune 0.6.0: whole-study copy by default, --files/--exclude-files, --institution, --anonymize example spec (04c5e0e)
- Add failing test: an --anonymize copy must load study info (e451357)
- unixtime_to_datetime returns None for a missing value (3dd14f3)
- Add failing tests: a pruner spec can declare anonymize: true (db987ae)
- Pruner spec key anonymize: true — a custom anonymizing spec names output and record like --anonymize (1e3a121)

### CLI

- Add failing tests for the common CLI changes (1aef5e3)
- Common CLI changes: ParaVision chooser, --root everywhere, convert --batch, init only (a430405)
- Add failing tests: BIDS docs example, config path pruner_specs, api layout example (17e66ac)
- config path: add pruner_specs (30e58c8)

### Context maps

- Add failing tests for context map v3 value rules (698c7d9)
- Context map v3 value rules in brkraw.specs.context_map (6dc1571)
- Add failing tests for context map output and wiring (8a1745b)
- Context map output and wiring: layout_template, utils, collisions, split, --axis/--frames (de46ccd)
- Add failing tests for Choi review fixes, MethodName and schema removal; xfail scaling repro (fd34392)
- Fix Choi review findings; add MethodName; remove the old context map schema (5355f6a)
- Tests: the Method item without the vendor prefix is MethodBase (deae759)
- MethodBase: Method without the vendor prefix (51090fe)
- Add failing test: brkraw.api.layout is public (1150eed)
- Export brkraw.api.layout (config layout helpers) for the docs examples (1223b63)

### Scaling

- Add failing tests for per-frame VisuCoreDataSlope handling (d398f8c)
- Per-frame VisuCoreDataSlope/Offs: equal values in the header, different values per frame (8ddb389)
- Add failing tests for the slope layout rule; rename prune fix-2 test (bdcaabb)
- Slope/offset layout rule; exact equality only (b9ac831)
- Add failing tests for the scaling warnings and context map installation (70ad26c)
- Scaling warnings and installable shared context maps (82275b8)

### Documentation

- Docs for 0.6.0: context maps v3, BIDS example, prune, pruner specs, migration guide (8e55650)
- Docs: remove the two merged overview pages; installable base context maps, include lookup order, new warnings (db8154d)
