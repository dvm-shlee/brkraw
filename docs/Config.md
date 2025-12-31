# Config Reference

BrkRaw stores user configuration under the config root. By default this is
`~/.brkraw`, or you can override it with `BRKRAW_CONFIG_HOME`.

The main file is `config.yaml`. It is created by `brkraw init` unless you pass
`--no-config`.

## File layout

```bash
~/.brkraw/
  config.yaml
  rules/
  specs/
  transforms/
```

## `config.yaml` keys

The default file is created from the template below (values may be omitted in
your local file).

```yaml
brkraw_version: "0.5.0a"
config_spec_version: 0
log_level: INFO
output_width: 120
nifti_filename_template: "sub-<Subject.ID>_study-<Study.ID>_scan-<ScanID>_<Protocol>"
float_decimals: 6
rules_dir: rules
specs_dir: specs
transforms_dir: transforms
```

### `log_level`

Logging level for CLI output. Common values: `INFO`, `DEBUG`, `WARNING`.

### `output_width`

Column width used by CLI tables (for example `brkraw info`).

### `float_decimals`

Default rounding for floating-point values shown in info tables and derived
outputs (including affine formatting).

### `nifti_filename_template`

Filename template used by `brkraw tonii` when an explicit output name is not
provided. Available tags:

- `<Subject.ID>`
- `<Study.ID>`
- `<ScanID>`
- `<Method>`
- `<Protocol>`

You can include directory separators in the template to create subdirectories
under the output root. For example:

```plain
<Study.ID>/<Subject.ID>/<Protocol>/sub-<Subject.ID>_scan-<ScanID>
```

Values come from `brkraw info` output. Template substitutions are sanitized so
that only `A-Z`, `a-z`, and `0-9` remain. Spaces and special characters are
stripped.

### `rules_dir`, `specs_dir`, `transforms_dir`

Relative paths under the config root where rule/spec/transform files are
installed. Most users should keep the defaults.

## Managing config from CLI

Use `brkraw config` to inspect or clear the config directory. See
`docs/CLI-config.md` for details.
