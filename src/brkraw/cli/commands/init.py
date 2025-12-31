from __future__ import annotations
from typing import Optional

import argparse
import logging
import os
from datetime import date
from pathlib import Path

from brkraw.core import config as config_core
from brkraw.apps import addon as addon_app

logger = logging.getLogger("brkraw")


def cmd_init(args: argparse.Namespace) -> int:
    config_core.init(
        root=args.root,
        create_config=not args.no_config,
        exist_ok=not args.no_exist_ok,
    )
    logger.info("Initialized config at %s", config_core.paths(root=args.root).root)
    if args.install_example:
        installed = addon_app.install_examples(root=args.root)
        if installed:
            logger.info("Installed %d example file(s).", len(installed))
    shellrc = Path(args.shellrc) if args.shellrc else _default_shell_rc()
    if shellrc is not None:
        _install_shell_helpers(shellrc)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize config and install examples.",
    )
    init_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    init_parser.add_argument(
        "--no-config",
        action="store_true",
        help="Do not create config.yaml.",
    )
    init_parser.add_argument(
        "--no-exist-ok",
        action="store_true",
        help="Fail if the root directory already exists.",
    )
    init_parser.add_argument(
        "--install-example",
        action="store_true",
        help="Install example specs and rules.",
    )
    init_parser.add_argument(
        "--shell-rc",
        dest="shellrc",
        help="Append shell helpers to the specified rc file (defaults to ~/.zshrc or ~/.bashrc).",
    )
    init_parser.set_defaults(func=cmd_init)


def _install_shell_helpers(path: Path) -> None:
    marker = "# brkraw shell helpers"
    snippet = "\n".join(
        [
            f"{marker} (added {date.today().isoformat()})",
            "brkraw-set() {",
            "  if [ \"$#\" -eq 0 ]; then",
            "    brkraw set",
            "  else",
            "    eval \"$(brkraw set \"$@\")\"",
            "  fi",
            "}",
            "brkraw-unset() {",
            "  if [ \"$#\" -eq 0 ]; then",
            "    eval \"$(brkraw unset)\"",
            "  elif [ \"$1\" = \"-h\" ] || [ \"$1\" = \"--help\" ]; then",
            "    brkraw unset \"$@\"",
            "  else",
            "    eval \"$(brkraw unset \"$@\")\"",
            "  fi",
            "}",
            "",
        ]
    )
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if marker in content:
            logger.info("Shell helpers already present in %s", path)
            return
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = ""
    path.write_text(content + ("\n" if content and not content.endswith("\n") else "") + snippet, encoding="utf-8")
    logger.info("Appended shell helpers to %s", path)


def _default_shell_rc() -> Optional[Path]:
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if shell.endswith("zsh"):
        return home / ".zshrc"
    if shell.endswith("bash"):
        return home / ".bashrc"
    return None
