# Addons and CLI Plugins

This document describes BrkRaw's extensibility model: rules, specs, converter
entrypoints, and CLI plugins.

## Concepts

BrkRaw separates *selection logic* (rules) from *parameter mapping* (specs) and
*conversion overrides* (converter_entrypoint). This lets you compose behavior
without modifying core code.

### Rules

Rules select specs or converter entrypoints based on Paravision parameters. You
can check fields from `method`, `acqp`, `visu_pars`, and others. When a rule
matches, BrkRaw chooses the corresponding spec or converter override.

### Specs

Specs define how parameters are mapped into structured outputs:

- `info_spec` controls what `brkraw info` shows.
- `metadata_spec` controls how `get_metadata` builds sidecar JSON (for example,
  a BIDS-like schema).

### Converter entrypoints

Converter entrypoints provide optional override callables for:

- `get_dataobj`
- `get_affine`
- `get_nifti1image`

This makes it possible to swap in sequence-specific conversion logic. For
example, a rule can detect a particular sequence and route conversion through a
custom reconstruction path that reads from FID data.

## Composition model

Rules can select:

- a spec (rule + spec), or
- a converter override (rule + converter_entrypoint), or
- both.

This enables conditional conversion:

```plain
if method/acqp/visu parameters match X
  -> use spec A
  -> use converter entrypoint B
```

## Managing addons

Rules, specs, and transforms live in the config folder. Use the `addon` CLI to
install, list, and remove them:

- `brkraw addon add path/to/spec.yaml`
- `brkraw addon list`
- `brkraw addon rm "spec.yaml" --force`

See `assets/examples/` for working examples, including:

- MRS `info_spec` for controlling `brkraw info`
- `metadata_spec` for BIDS-like sidecar metadata

## Converter entrypoint roadmap

We plan to add a converter entrypoint for UNC's SORDINO sequence to
support the custom reconstruction pipeline.

## CLI plugins

BrkRaw supports CLI extensions via entrypoints, so new commands can be shipped
without touching the core repository. Planned plugins include:

- BIDS tooling (legacy tools from earlier versions)
- Backup/export utilities
- GUI tools

These will be distributed as external plugins and registered via the
`brkraw.cli` entrypoint group.
