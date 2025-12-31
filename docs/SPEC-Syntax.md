# SPEC Syntax Guide (core.remapper module)

This module maps Bruker parameter files into a structured output dictionary.

## Rule Structure

Each top-level key in the spec defines one output field (supports dotted keys
for nesting):

```yaml
__meta__:
  name: "MRS Info Spec"
  description: "Metadata mapping for PRESS/STEAM scans."
  transforms_source: "mrs_transforms.py"

out.some_field:
  sources:
    - file: method
      key: PVM_SPackArrNSlices
```

`__meta__.transforms_source` is optional. When present, `load_spec` resolves the
path relative to the spec file (absolute paths are allowed). It can also be a
list of transform files; later files override earlier ones. For grouped specs
like `study.yaml` with multiple sections, put `__meta__` under each section.
`__meta__.include` is optional. When present, it can be a string or list of
relative/absolute spec paths to merge before the current spec. Keys in the
current spec override included keys unless `__meta__.include_mode` is set to
`strict`, which raises on conflicts.

Rules support:

- `sources`: resolve a value from one or more parameter sources.
- `inputs`: build a dict of named inputs, optionally transformed.
- `transform`: apply a transform (string or list of strings).

Exactly one of `sources` or `inputs` is required.
If `transform` is omitted, the resolved value (or the inputs dict) is returned as-is.

To validate the spec against the schema:

```python
from brkraw.core.remapper import map_parameters

result = map_parameters(scan, spec, validate=True)
```

## Input Specs

When using `inputs`, each input has one of:

- `sources`: list of source selectors.
- `const`: literal value.
- `ref`: dotted path to a previously resolved output value.

Optional modifiers:

- `transform`: apply transform(s) after resolving the input.
- `default`: fallback when sources are missing.
- `required`: if true, missing input raises an error.

Example:

```yaml
out.joined:
  inputs:
    a:
      sources:
        - file: acqp
          key: ACQ_scan_name
    b:
      const: 3
  transform: join_fields
```

More examples:

```yaml
out.with_default:
  inputs:
    count:
      sources:
        - file: visu_pars
          key: VisuCoreFrameCount
          reco_id: 1
      default: 1
  transform: passthrough
```

```yaml
out.required_field:
  inputs:
    subject_id:
      sources:
        - file: subject
          key: SUBJECT_id
      required: true
  transform: as_string
```

```yaml
out.derived:
  inputs:
    base:
      sources:
        - file: method
          key: PVM_SPackArrNSlices
      transform: to_int
    prior:
      ref: out.joined
  transform: combine_base_and_prior
```

```python
def to_int(value):
    return int(value)

def combine_base_and_prior(base, prior):
    return f"{prior}:{base}"
```

## Sources

Each `sources` entry supports:

- `file`: one of `method`, `acqp`, `visu_pars`, `reco`, `subject`.
- `key`: parameter name inside that file.
- `reco_id`: used for `visu_pars`/`reco` to select a reco.

If multiple sources are listed, the first available value wins.

## Transforms

Transforms are functions referenced by name. When used with `inputs`:

- The first transform receives inputs as kwargs.
- If a list is provided, subsequent transforms receive the previous output.

Example:

```yaml
out.combined:
  inputs:
    a: { const: "foo" }
    b: { const: "bar" }
  transform: [join_fields, upper]
```

```python
def join_fields(a, b):
    return f"{a}_{b}"

def upper(value):
    return value.upper()
```

## Study Rules

When a Study-like object is passed as the source:

- Only `file: subject` is allowed.
- At least one `subject` source must be present.
