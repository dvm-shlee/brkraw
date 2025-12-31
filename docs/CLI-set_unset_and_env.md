# CLI: Set, Unset, Env

These commands manage environment defaults for repeated CLI use.

## Shell helpers

Install helpers into your shell rc:

- `brkraw init --shell-rc ~/.zshrc`

Then you can use:

- `brkraw-set ...` (exports vars in the current shell)
- `brkraw-unset ...` (unsets vars in the current shell)

## brkraw set

Emit `export` statements for environment defaults.

Examples:

- `brkraw set -p /path/to/study -s 3 -r 1`
- `brkraw set --output-format nii.gz`
- `brkraw set --tonii-option OUTPUT=./out --tonii-option SIDECAR=1`

Tonii options (set as `BRKRAW_TONII_<KEY>`):

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`
- `SIDECAR`, `UNWRAP_POSE`, `FLIP_X`
- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`
- `XYZ_UNITS`, `T_UNITS`, `HEADER`, `OUTPUT_FORMAT`

## brkraw unset

Emit `unset` statements. Behavior:

- No args: unset all BrkRaw defaults.
- `--tonii-option` without a key: unset all tonii defaults.
- `--tonii-option KEY` (repeatable): unset selected tonii keys.
- `--path`, `--scan-id`, `--reco-id`, `--param-key`, `--param-file`, `--output-format`
  unset those specific defaults.

Examples:

- `brkraw unset`
- `brkraw unset --path --scan-id`
- `brkraw unset --tonii-option`
- `brkraw unset --tonii-option OUTPUT --tonii-option SCAN_ID`

## brkraw env

Show current environment defaults.

Example:

- `brkraw env`
