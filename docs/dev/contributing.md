# Contribution Guide

Thank you for your interest in contributing to BrkRaw. This guide explains how
the project is extended, and clarifies which kinds of changes belong in core
versus addons or plugins.

We welcome contributions across a wide range of areas, including:

- New sequence support (rules, specs, and converter hooks)
- Custom reconstruction pipelines (FID-based or other specialized paths)
- Image denoising or ML-powered workflows
- CLI plugins and tooling built on top of the BrkRaw API

Before opening an issue or pull request, please start with a GitHub Discussion
so we can align on scope and choose the appropriate extension path. For core
changes, we follow a clear progression:

Discussion proposal → Issue(s) → Pull request

---

## Development environment (VSCode recommended)

We track a shared `.vscode/` directory to provide consistent tasks and settings
across contributors.

1) Create a virtual environment and install development dependencies.

With [uv](https://docs.astral.sh/uv/) (recommended; uses the tracked
`uv.lock` and `.python-version`):

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest
```

Keep `--extra dev` on `uv run` too; without it uv syncs the environment back
to the runtime dependencies only and removes the development tools.

Or with pip:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

2. In VSCode, select the workspace interpreter (`.venv/bin/python`).

3. Optional: run predefined tasks from the Command Palette
   (`Tasks: Run Task`). All of them use `uv` and the tracked `uv.lock`:

| Task | What it does |
| --- | --- |
| `Setup: uv sync (dev)` | Create or update `.venv` with the development tools |
| `Test: tests` | The synthetic test suite, the same one CI runs |
| `Validate: real data (manual)` | Checks on approved real data (see below); not run by CI |
| `Docs: MkDocs serve` | Serve the documentation locally |
| `Release: prep (local, no network)` | Bump the version files and rename the `Unreleased` notes section |
| `Release: open upstream PR (dry run)` | Print every release step; writes nothing and uses no network |
| `Release: open upstream PR (--repo BrkRaw/brkraw)` | Open the release PR (see "Release and publishing") |

There is deliberately no task that creates or pushes a tag.

---

## Tests and manual checks on real data

`tests/` is the automatic suite that CI runs on every push. It uses synthetic
data only (the PvDataset builder in `tests/helpers.py`) and never reads a real
study, so it passes the same way on every machine.

Checks that need real, approved anonymized ParaVision studies are not tests.
They are kept in `scripts/validate/` and are run by hand, for example before a
release or when you change prune, convert, context maps, scaling or study info.
CI does not run them, and a plain `pytest` does not collect them (the file name
starts with `check_`, and `pytest` collects `test_*.py`).

The approved zips (ParaVision 5.1, 6.0.1 and 360.3.x) are kept outside Git in a
folder next to your checkout, `<checkout>/../agent-fixtures`, with a README
that lists each zip, its SHA-256 and whether it is approved. Only approved zips
with a matching SHA-256 are used, and they are copied to a temporary folder;
nothing is written in the folder. To use another folder, set
`BRKRAW_AGENT_FIXTURES=/path/to/agent-fixtures`. If the folder is missing the
run stops with a message (it does not skip).

```bash
pytest -v scripts/validate/check_agent_fixtures.py
```

`check_agent_fixtures.py` holds the checks that were moved out of `tests/`:
the byte-identical default prune of the 5.1 zips, a same-name context map
converting every scan of the 5.1, 6.0.1 and 360.3.x zips, scans with one equal
slope per frame keeping raw data, context map values read from real scan info
leaving it unchanged, and the self-test of the fixture finder. Each of these
has a synthetic counterpart in `tests/`.

---

## Development workflow (branches, release notes, tests)

Maintainers develop on a fork (remote `origin`). `BrkRaw/brkraw` (remote
`upstream`) receives release pull requests only, and only its workflows create
tags and publish packages.

**Branches**

- Work on `feat/<topic>`, `fix/<topic>`, `docs/<topic>` or `test/<topic>`,
  branched from the fork's `main`.
- Open a pull request into the fork's `main`. Merge it as soon as CI and review
  pass. The fork's `main` is always the next release candidate, so packages
  that depend on brkraw (viewer, hooks) can test against it.
- `release/<version>` holds only the version bump and the release-note heading.
  It is the only kind of branch proposed to `BrkRaw/brkraw`.
- After the upstream merge, fast-forward the fork's `main` to `upstream/main`
  so both stay the same.

**Release notes**

- `RELEASE_NOTES.md` is written by hand and becomes the text of the GitHub
  release and of the announcement.
- Every feature or fix pull request adds its entry under a `## Unreleased`
  heading (if it is missing, add it above the newest `## Changes since`
  section): what changed for users and what they need to do.
- At release time `scripts/release_prep.py` changes only the first heading
  (`# Release v<version>`), the `Date:` line, and renames `## Unreleased` to
  `## Changes since <previous version>`. It does not rewrite or generate the
  text.

**Tests**

- CI runs `tests/` (synthetic data only) on every push and pull request that
  touches `src/`, `tests/`, `scripts/` or `pyproject.toml`.
- By hand, before every release candidate and release: the real-data checks in
  `scripts/validate/` (task `Validate: real data (manual)`). brkraw-viewer also
  has a manual GUI smoke test.
- Documentation changes are checked by the Docs check workflow
  (`mkdocs build --strict`).

**Versions and tags**

- Versions follow PEP 440 without a leading `v`: `0.6.1rc1`, `0.6.1rc2`, then
  `0.6.1`. The tag has the same text as the version.
- Tags are created only by the upstream `Release On Merge` workflow. Do not
  create tags by hand and never push tags to `upstream` (`git push --tags` or
  `--follow-tags`): a pushed tag does not start a release, but it would leave
  a tag that may point at a different commit than the released one.

---

## CLI extensions

BrkRaw supports CLI extensions through an entrypoint mechanism, allowing new
subcommands to be developed and distributed independently of the core
repository.

- Entrypoint group: `brkraw.cli`
- Intended for custom workflows or project-specific helpers

See `extensions/addons-and-plugins.md` for an overview of the extension model.

---

## Extension points

Most customization can be implemented without modifying core code:

- Install rules, specs, and transforms using the `addon` CLI
- Define or update runtime `context_map` entries to map scanner context to
  specs, rules, and transforms
- Provide `converter_hook` overrides for specialized conversion logic
- Ship standalone CLI plugins via the `brkraw.cli` entrypoint

---

## Rule, spec, and transform workflow

Rules determine which specs and converter hooks apply to a given scan. Specs map
Bruker parameter files into structured outputs. Transforms are Python helpers
used during spec evaluation.

This composition model enables conditional workflows, such as applying
different metadata schemas per sequence, without editing core code.

Recommended references:

- `extensions/rules.md`
- `extensions/specs.md`

---

## Converter hooks (custom conversion)

Converter hooks override conversion helpers such as `get_dataobj`,
`get_affine`, and `convert`. They are registered via the
`brkraw.converter_hook` entrypoint and may be selected conditionally by rules.

This design allows sequence-specific reconstruction pipelines while preserving
BrkRaw's standard handling of metadata, sidecars, and output layouts.

Converter hooks are especially useful for custom MRI sequences with bespoke
reconstruction requirements. In most cases, they should be packaged as small,
independent plugins.

---

## Layout design and data structure

brkraw has two independent layouts:

- the config layout in `config.yaml` (`output.layout_entries` with `key`,
  `entry`, `sep`, or `output.layout_template` with `{Key}` tags);
- a context map's own `__meta__.layout_template`, which uses namespace tags and
  `utils` values and is used instead of the config layout for that dataset.

See [Layout and naming](../extensions/layout.md) and
[Context maps](../extensions/context-map.md).

---

## Core development policy

Core changes are limited to maintaining compatibility with ParaVision layouts
and metadata conventions. All other customization should be implemented as
addons (rules, specs, transforms, context maps) or external plugins.

If you believe a change must live in core, start with a GitHub Discussion and
explain why the behavior cannot be implemented through existing extension
mechanisms. Once agreed, open issue(s) for the scoped work and combine them into
a single pull request.

---

## Defaults we welcome contributions for

We actively welcome proposals for default rules and specs to ship with BrkRaw,
particularly for modality-specific workflows. If you work with specific Bruker
sequences, consider contributing:

- Improved `info_spec` mappings for `brkraw info` or `BrukerLoader.info`
- `metadata_spec` mappings aligned with BIDS or lab standards
- Rules that select specs based on `method`, `acqp`, or `visu_pars`
- Reusable `context_map` patterns for common lab workflows

Documentation contributions are also valuable, including:

- End-to-end use cases combining rules, specs, and context maps
- Modality-specific tutorials (for example DWI, fMRI, or MRS)
- Corrections or clarifications to existing documentation

Even small improvements, such as clearer parameter labels, are useful. Please
open a Discussion with sequence details and the parameter files you rely on.

---

## Packaging and distribution

We encourage authors to package addons and plugins as standalone repositories so
they can be installed and versioned independently. This simplifies sharing
tools across labs and projects.

---

## Release and publishing (GitHub Actions)

A release is one pull request from the fork branch `release/<version>` into
`BrkRaw/brkraw` `main`. Merging it with the `release` label does the rest.

1. Run the real-data checks (`Validate: real data (manual)`) on the fork's
   `main`, and make sure the notes have an `## Unreleased` section.
2. Create the branch: `git switch -c release/<version> origin/main`.
3. Run `Release: open upstream PR (dry run)` and read the plan. It writes no
   file and uses no network.
4. Run `Release: open upstream PR (--repo BrkRaw/brkraw)`
   (`scripts/release_pr.py --repo BrkRaw/brkraw --version <version>`). It
   refuses to run unless the branch is `release/<version>`, the tree is
   clean and `--repo` is the `upstream` remote. It then refreshes the
   contributors list, runs `release_prep.py`, runs `pytest -q tests`, makes one
   commit, pushes the branch only
   (`git push --no-follow-tags origin HEAD:refs/heads/release/<version>`),
   opens the PR on `BrkRaw/brkraw` and adds the `release` label (also for
   `a`/`b`/`rc` versions).
5. Review the PR and wait for CI. Merge it with a merge commit, not squash or
   rebase: `gh pr merge <number> --repo BrkRaw/brkraw --merge`.
6. The workflows then run on `BrkRaw/brkraw` by themselves:
   - `Release On Merge` finds the PR of the merge commit, requires the
     `release` label and a change to `src/brkraw/__init__.py`, checks that the
     tag equals `__version__` (`scripts/verify_release_version.py`), tags the
     merge commit and starts `Create Release`.
   - `Create Release` checks the tag again, creates the GitHub release with
     `RELEASE_NOTES.md` as its text (a pre-release for `a`, `b` and `rc`),
     posts it in the Discussions category "Announcements" if that exists, and
     starts `Publish Package` (TestPyPI for a pre-release, PyPI otherwise). For
     a final release it also starts `Deploy Docs`.
   - `Publish Package` checks the tag once more, builds, runs `twine check`
     and publishes with trusted publishing.
7. Fast-forward the fork: `git fetch upstream --tags`,
   `git switch main`, `git merge --ff-only upstream/main`,
   `git push origin main`.

If `Release On Merge` skipped the tag (no label, or no PR found for the merge
commit) and nothing else was merged since, start it by hand:
`gh workflow run release_on_merge.yml --repo BrkRaw/brkraw -f tag=<version> -f run_release=true`.
If the tag exists but a later step failed, run that workflow again with
`gh workflow run release.yml --repo BrkRaw/brkraw -f tag=<version>` or
`gh workflow run publish.yml --repo BrkRaw/brkraw -f target=pypi -f tag=<version>`.
These re-runs work for tags made after `scripts/verify_release_version.py` was
added; an older tag (0.6.1rc2 and before) does not contain that script, so the
version check stops the re-run.

`gh` needs a token with the `workflow` scope to merge a pull request that
changes `.github/workflows/` (`gh auth refresh -s workflow`).

The Zenodo DOI badge (`docs/assets/zenodo_badge.svg`) is updated after a
release with `scripts/update_zenodo_badge.py`, which only rewrites the file;
commit it on a `docs/` branch and send it through the fork like any other
change.

---

## Community

If you build something useful, please start a GitHub Discussion. We plan to
periodically highlight community addons and plugins on the BrkRaw site.

---

## Contributors

See `docs/dev/contributors.md` for the current list of contributors.
