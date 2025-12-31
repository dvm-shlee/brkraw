# Getting Started

This guide covers the minimum setup steps and common first-run tasks.

## Install BrkRaw (placeholder)

Installation instructions will be added once the project is published on PyPI.

## Initialize the config directory

Run the initializer to create the config root, `config.yaml`, and default
folders for rules/specs/transforms.

```bash
brkraw init
```

Optional flags:

- `--root` to override the config root.
- `--no-config` to skip creating `config.yaml`.
- `--no-exist-ok` to fail if the root already exists.
- `--install-example` to install the example rules/specs from `assets/examples`.
- `--shell-rc` to append shell helper functions to a specific rc file.

## Add example specs and rules

If you want the example rule/spec set, install them during init:

```bash
brkraw init --install-example
```

You can also add them later with:

```bash
brkraw addon add assets/examples/rules/10-metadata.yaml
brkraw addon add assets/examples/specs/metadata_common.yaml
```

## Shell helper functions (optional)

The init command can append `brkraw-set` and `brkraw-unset` helpers to your
shell rc file (default: `~/.zshrc` or `~/.bashrc`).

```bash
brkraw init --shell-rc ~/.zshrc
```

After reloading your shell, you can use:

```bash
brkraw-set --path /path/to/dataset.zip --scan-id 1
brkraw-unset --scan-id
```

## First conversions

Inspect a dataset:

```bash
brkraw info /path/to/dataset.zip
```

Convert a scan to NIfTI:

```bash
brkraw tonii /path/to/dataset.zip -s 1
```

See `docs/CLI-info_and_params.md` and `docs/CLI-tonii_and_tonii_all.md` for
additional options.
