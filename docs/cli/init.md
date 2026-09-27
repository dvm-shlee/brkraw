# init

Create the brkraw config folder, and optionally install the default specs and
rules and the shell helpers.

```bash
brkraw init                              # asks each step
brkraw init --install-default --yes      # no questions (see the note on --yes)
brkraw init --root /path/to/config       # another config folder
```

The config folder is `BRKRAW_CONFIG_HOME`, else `~/.brkraw`. Every command
also takes `--root DIR`.

!!! note "Changed in 0.6.0"
    `brkraw config init` was removed; `brkraw init` is the one command that
    creates the config folder.

## What it does

Asked step by step without `--yes`:

1. create the config folder and `config.yaml` (you can change the values);
2. install the default specs, rules, pruner specs and transforms
   (`--install-default`), needed for sidecar metadata (`-c`);
3. add the shell helpers `brkraw-set` and `brkraw-unset` to your shell file.

!!! warning "`--yes` also changes your shell file"
    With `--yes`, brkraw writes `config.yaml` with the default values and,
    when your shell is zsh or bash, **appends the shell helpers to
    `~/.zshrc` or `~/.bashrc`** (once; a second run sees them and does
    nothing). This is also true for `--yes --install-default`. To keep your
    shell file unchanged, run `brkraw init` without `--yes` and answer "no"
    to the shell helper question.

## Options

| Option | Meaning |
| --- | --- |
| `--root ROOT` | Config folder to create or use. |
| `--no-exist-ok` | Stop if the folder already exists. |
| `--config` | Create or replace `config.yaml` only (asks for the values). |
| `--install-default` | Install the default specs, rules, pruner specs and transforms. |
| `--shell-rc FILE` | Append the shell helpers to this file. |
| `--yes` | No questions; use the defaults (see the warning above). |

## Shell helpers

```bash
brkraw-set -p /path/to/study -s 3    # same as: eval "$(brkraw session set -p /path/to/study -s 3)"
brkraw-unset                         # clear the session defaults
```

See [session](session.md).
