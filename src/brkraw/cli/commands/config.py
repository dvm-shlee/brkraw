from __future__ import annotations
from typing import List, Optional

import argparse
import logging
import os
from pathlib import Path

from brkraw.core import config as config_core

logger = logging.getLogger("brkraw")


def cmd_config(args: argparse.Namespace) -> int:
    handler = getattr(args, "config_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def cmd_init(args: argparse.Namespace) -> int:
    config_core.init(
        root=args.root,
        create_config=not args.no_config,
        exist_ok=not args.no_exist_ok,
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    paths = config_core.paths(root=args.root)
    logger.info("Config root: %s", paths.root)
    logger.info("- config.yaml: %s", paths.config_file)
    logger.info("- specs dir:   %s", paths.specs_dir)
    logger.info("- rules dir:   %s", paths.rules_dir)
    logger.info("- transforms:  %s", paths.transforms_dir)
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    paths = config_core.paths(root=args.root)
    if not paths.root.exists():
        return 0
    logger.info("Config root: %s", paths.root)
    logger.info("- config.yaml: %s", paths.config_file)
    logger.info("- rules dir:   %s", paths.rules_dir)
    logger.info("- specs dir:   %s", paths.specs_dir)
    logger.info("- transforms:  %s", paths.transforms_dir)
    shellrc = Path(args.shellrc) if args.shellrc else _default_shell_rc()
    if shellrc is not None:
        action = "remove helpers" if not args.keep_shell_helpers else "keep helpers"
        logger.info("- shell rc (%s): %s", action, shellrc)
    if not args.yes:
        prompt = f"Remove brkraw config at {paths.root}? [y/N]: "
        reply = input(prompt).strip().lower()
        if reply not in {"y", "yes"}:
            return 1
    config_core.clear(
        root=args.root,
        keep_config=args.keep_config,
        keep_rules=args.keep_rules,
        keep_specs=args.keep_specs,
        keep_transforms=args.keep_transforms,
    )
    if not args.keep_shell_helpers:
        if shellrc is None:
            logger.error("Could not determine shell rc path for removal.")
            return 1
        if not _remove_shell_helpers(shellrc):
            logger.info("No brkraw shell helpers found in %s", shellrc)
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    path = config_core.get_path(args.name, root=args.root)
    logger.info("%s", path)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    config_parser = subparsers.add_parser(
        "config",
        help="Manage brkraw config locations.",
    )
    config_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    config_parser.set_defaults(func=cmd_config, parser=config_parser)
    config_sub = config_parser.add_subparsers(dest="config_command")

    init_parser = config_sub.add_parser("init", help="Create the config folders.")
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
    init_parser.set_defaults(config_func=cmd_init)

    show_parser = config_sub.add_parser("show", help="Print resolved config paths.")
    show_parser.set_defaults(config_func=cmd_show)

    clear_parser = config_sub.add_parser("clear", help="Remove brkraw config files.")
    clear_parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    clear_parser.add_argument(
        "--keep-config",
        action="store_true",
        help="Keep config.yaml.",
    )
    clear_parser.add_argument(
        "--keep-rules",
        action="store_true",
        help="Keep rules directory.",
    )
    clear_parser.add_argument(
        "--keep-specs",
        action="store_true",
        help="Keep specs directory.",
    )
    clear_parser.add_argument(
        "--keep-transforms",
        action="store_true",
        help="Keep transforms directory.",
    )
    clear_parser.add_argument(
        "--keep-shell-helpers",
        action="store_true",
        help="Keep brkraw-set/brkraw-unset helpers in shell rc.",
    )
    clear_parser.add_argument(
        "--shell-rc",
        dest="shellrc",
        help="Shell rc file to update when removing helpers (defaults to ~/.zshrc or ~/.bashrc).",
    )
    clear_parser.set_defaults(config_func=cmd_clear)

    path_parser = config_sub.add_parser("path", help="Print a specific config path.")
    path_parser.add_argument(
        "name",
        choices=["root", "config", "rules", "specs", "transforms"],
        help="Path key to print.",
    )
    path_parser.set_defaults(config_func=cmd_path)


def _remove_shell_helpers(path: Path) -> bool:
    if not path.exists():
        return False
    marker = "# brkraw shell helpers"
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines: List[str] = []
    removed = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(marker):
            removed = True
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                i += 1
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            continue
        new_lines.append(line)
        i += 1
    if removed:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return removed


def _default_shell_rc() -> Optional[Path]:
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if shell.endswith("zsh"):
        return home / ".zshrc"
    if shell.endswith("bash"):
        return home / ".bashrc"
    return None
