# CLI: config

Manage the configuration root and related paths.

## brkraw config init

Create the config root and optional `config.yaml`.

Examples:

- `brkraw config init`
- `brkraw config init --no-config`

## brkraw config show

Show resolved config values as YAML.

Example:

- `brkraw config show`

Defaults are included even if the key is missing from `config.yaml`.

## brkraw config where

Print the config root path.

Example:

- `brkraw config where`

## brkraw config clear

Remove config data with optional selective retention.

Examples:

- `brkraw config clear`
- `brkraw config clear --keep-specs --keep-rules`
- `brkraw config clear --keep-pruner-specs`
- `brkraw config clear --keep-maps`
- `brkraw config clear --keep-shell-helpers`

## brkraw config path

Print a specific config path.

Example:

- `brkraw config path specs`
- `brkraw config path pruner_specs`
- `brkraw config path maps`

## brkraw config set

Set a config key to a YAML value.

Example:

- `brkraw config set output.format_fields '[{key: Subject.ID, entry: sub, hide: false}]'`
- `brkraw config set output.format_spec=metadata_common`
- `brkraw config set logging.level=DEBUG`

## brkraw config unset

Remove a config key.

Example:

- `brkraw config unset output.format_spec`

## brkraw config reset

Reset `config.yaml` to defaults.

Example:

- `brkraw config reset --yes`

## brkraw config edit

Open `config.yaml` in the configured editor (`editor` or `$EDITOR`).

Example:

- `brkraw config edit`
