from __future__ import annotations

import re
import os
import shutil
import subprocess
import argparse
import sys
from typing import Callable, Dict, List, Optional, Tuple
from ..core.entrypoints import list_entry_points as _iter_entry_points

from brkraw import __version__
from brkraw.core import config as config_core

PLUGIN_GROUP = "brkraw.cli"
HELP_CATEGORY_ORDER = ("Data", "Workspace", "Extensions")
HELP_COMMAND_ORDER = {
    "info": 0,
    "params": 1,
    "convert": 2,
    "convert-batch": 3,
    "prune": 4,
    "init": 5,
    "config": 6,
    "cache": 7,
    "session": 8,
    "addon": 9,
    "hook": 10,
}
HELP_CATEGORY_BY_COMMAND = {
    "info": "Data",
    "params": "Data",
    "convert": "Data",
    "convert-batch": "Data",
    "prune": "Data",
    "init": "Workspace",
    "config": "Workspace",
    "cache": "Workspace",
    "session": "Workspace",
    "addon": "Extensions",
    "hook": "Extensions",
}


def _run_capture(cmd: list[str]) -> str:
    p = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return p.stdout


def _pv_autoset_env() -> None:
    if shutil.which("pvcmd") is None:
        return

    p = subprocess.run(["pvcmd", "-e", "ParxServer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if p.returncode != 0:
        return

    out = _run_capture(["pvcmd", "-a", "ParxServer", "-r", "ListPs", "-csv"])
    matches = [line for line in out.splitlines() if "REQUEST_ATTR" in line]

    if len(matches) == 0:
        raise SystemExit("ERROR: No ps entry with REQUEST_ATTR found")
    if len(matches) > 1:
        msg = "ERROR: Multiple ps entries with REQUEST_ATTR found\n" + "\n".join(matches)
        raise SystemExit(msg)

    line = matches[0]
    parts = line.split(";")

    m = None
    for f in parts:
        f = f.strip()
        m = re.match(r"^(?P<exp_path>.+)/(?P<scan_id>\d+)/pdata/(?P<reco_id>\d+)$", f)
        if m:
            break

    if not m:
        raise SystemExit("ERROR: No valid <exp_path>/<scan_id>/pdata/<reco_id> path found")

    exp_path = m.group("exp_path")
    scan_id = m.group("scan_id")
    reco_id = m.group("reco_id")

    os.environ["BRKRAW_PATH"] = exp_path
    os.environ["BRKRAW_SCAN_ID"] = scan_id
    os.environ["BRKRAW_RECO_ID"] = reco_id


def _register_entry_point_commands(
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> None:
    for ep in _iter_entry_points(PLUGIN_GROUP):
        try:
            register = ep.load()
        except Exception as exc:  # noqa: BLE001 - best-effort plugin load
            print(f"warning: failed to load entry point {ep.name!r}: {exc}")
            continue
        if not callable(register):
            raise TypeError("entry point must be callable (register(subparsers)).")
        register(subparsers)

    preferred = [
        "init",
        "config",
        "cache",
        "session",
        "info",
        "params",
        "convert",
        "convert-batch",
        "prune",
        "addon",
        "hook",
    ]
    preferred_set = set(preferred)
    ordered = [name for name in preferred if name in subparsers.choices]
    ordered += [name for name in subparsers.choices if name not in preferred_set]
    subparsers.choices = {name: subparsers.choices[name] for name in ordered}
    choices_actions = getattr(subparsers, "_choices_actions", None)
    if choices_actions:
        action_map = {action.dest: action for action in choices_actions}
        ordered_actions = [action_map[name] for name in ordered if name in action_map]
        ordered_actions += [
            action for action in choices_actions if action.dest not in ordered
        ]
        subparsers._choices_actions = ordered_actions  # type: ignore[attr-defined]


def _help_category_for_command(name: str, parser: argparse.ArgumentParser) -> str:
    category = getattr(parser, "_brkraw_help_category", None)
    if isinstance(category, str) and category.strip():
        return category.strip()

    category = getattr(parser, "help_category", None)
    if isinstance(category, str) and category.strip():
        return category.strip()

    return HELP_CATEGORY_BY_COMMAND.get(name, "Extensions")


def _help_order_for_command(name: str) -> Tuple[int, str]:
    return (HELP_COMMAND_ORDER.get(name, 999), name)


def _render_help(
    parser: argparse.ArgumentParser,
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> str:
    formatter = parser._get_formatter()
    formatter.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)
    if parser.description is not None:
        formatter.add_text(parser.description)

    option_groups = [group for group in parser._action_groups if group.title == "options"]
    for group in option_groups:
        formatter.start_section(group.title)
        if group.description is not None:
            formatter.add_text(group.description)
        formatter.add_arguments(
            action
            for action in group._group_actions
            if action is not subparsers
        )
        formatter.end_section()

    actions_by_name = {action.dest: action for action in getattr(subparsers, "_choices_actions", [])}
    grouped: Dict[str, List[argparse.Action]] = {}
    for name, action in actions_by_name.items():
        command_parser = subparsers.choices.get(name)
        if command_parser is None:
            continue
        category = _help_category_for_command(name, command_parser)
        grouped.setdefault(category, []).append(action)

    categories = [category for category in HELP_CATEGORY_ORDER if category in grouped]
    categories.extend(sorted(category for category in grouped if category not in HELP_CATEGORY_ORDER))

    for category in categories:
        formatter.start_section(category)
        formatter.add_arguments(sorted(grouped[category], key=lambda action: _help_order_for_command(action.dest)))
        formatter.end_section()

    formatter.add_text(parser.epilog)
    return formatter.format_help()


def _print_help(
    parser: argparse.ArgumentParser,
    subparsers: argparse._SubParsersAction,  # type: ignore[name-defined]
) -> None:
    print(_render_help(parser, subparsers), end="")


def main(argv: Optional[List[str]] = None) -> int:
    config_core.configure_logging()
    parser = argparse.ArgumentParser(
        prog="brkraw",
        description="BrkRaw command-line interface.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s v{}".format(__version__)
    )

    subparsers = parser.add_subparsers(
        title="Sub-commands",
        description=(
            "Choose one of the sub-commands below. For details on a specific "
            "command, run: brkraw <command> -h."
        ),
        dest="command",
        metavar="command",
    )

    _register_entry_point_commands(subparsers)
    _pv_autoset_env()

    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        _print_help(parser, subparsers)
        return 2
    if argv_list[0] in {"-h", "--help"}:
        _print_help(parser, subparsers)
        return 0

    args = parser.parse_args(argv_list)
    if not hasattr(args, "func"):
        _print_help(parser, subparsers)
        return 2
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
