# CLI: config

Manage the configuration root and related paths.

## brkraw config init

Create the config root and optional `config.yaml`.

Examples:

- `brkraw config init`
- `brkraw config init --no-config`

## brkraw config show

Show resolved config paths.

Example:

- `brkraw config show`

## brkraw config clear

Remove config data with optional selective retention.

Examples:

- `brkraw config clear`
- `brkraw config clear --keep-specs --keep-rules`
- `brkraw config clear --keep-shell-helpers`

## brkraw config path

Print a specific config path.

Example:

- `brkraw config path specs`
