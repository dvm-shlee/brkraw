# CLI: addon

Manage installed specs, rules, and transforms.

## brkraw addon add

Install a spec or rule file.

Example:

- `brkraw addon add path/to/spec.yaml`

## brkraw addon list

List installed specs, rules, and transforms.

Example:

- `brkraw addon list`

## brkraw addon rm

Remove installed addons by filename (wildcards supported).

Examples:

- `brkraw addon rm metadata_func.yaml`
- `brkraw addon rm "*.yaml" --kind spec --force`

Notes:

- Dependency checks run by default; use `--force` to remove anyway.
- `--kind` can limit removal to `spec`, `rule`, or `transform`.
