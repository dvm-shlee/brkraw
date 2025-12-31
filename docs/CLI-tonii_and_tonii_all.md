# CLI: tonii and tonii_all

These commands convert Paravision datasets to NIfTI and optionally write JSON
sidecars.

## brkraw tonii

Convert a single dataset. If `-s/--scan-id` is omitted, all scans and recos are
converted.

Examples:

- `brkraw tonii /path/to/study -s 3 -r 1 -o out`
- `brkraw tonii /path/to/study --sidecar`
- `brkraw tonii /path/to/study -o out` (all scans, all recos)

Notes:

- `-o` with `.nii` or `.nii.gz` writes a single file.
- `-o` without an extension is treated as a directory when converting all scans.
- Multiple slice packs are written with `_slpackN` suffixes.

## brkraw tonii_all

Convert every dataset found under a root folder (subdirectories and zip files).

Examples:

- `brkraw tonii_all /path/to/root -o /path/to/out`

Notes:

- `-o` must be a directory for `tonii_all`.
- `tonii_all` always converts all scans and recos.
- Each dataset path is logged before conversion.

## Filename templates

NIfTI filenames are built from `nifti_filename_template` in `config.yaml`.
Tags are replaced using study/subject/scan info:

- `<Subject.ID>`
- `<Study.ID>`
- `<ScanID>`
- `<Method>`
- `<Protocol>`

Values from tags are sanitized to alphanumeric only. Template separators like
`_`, `-`, and `/` are preserved, so you can create folders:

Example:

```
nifti_filename_template: "<Study.ID>/<Subject.ID>/<Protocol>/sub-<Subject.ID>_scan-<ScanID>"
```

## Environment defaults

You can set defaults via `brkraw set --tonii-option KEY=VALUE`.
Common keys:

- `OUTPUT`, `PREFIX`, `SCAN_ID`, `RECO_ID`
- `SIDECAR`, `UNWRAP_POSE`, `FLIP_X`
- `OVERRIDE_SUBJECT_TYPE`, `OVERRIDE_SUBJECT_POSE`
- `XYZ_UNITS`, `T_UNITS`, `HEADER`, `OUTPUT_FORMAT`
