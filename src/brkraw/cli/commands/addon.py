from __future__ import annotations
from typing import Dict

import argparse
import logging
from brkraw.core import config as config_core
from brkraw.core import formatter
from brkraw.apps import addon as addon_app

logger = logging.getLogger("brkraw")


def cmd_addon(args: argparse.Namespace) -> int:
    handler = getattr(args, "addon_func", None)
    if handler is None:
        args.parser.print_help()
        return 2
    return handler(args)


def _normalize_row(row: Dict[str, str]) -> Dict[str, object]:
    name = row.get("name", "")
    desc = row.get("description", "")
    category = row.get("category", "")
    name_cell: object = name
    desc_cell: object = desc
    category_cell: object = category
    if row.get("name_unknown") == "1":
        name_cell = {"value": name, "color": "gray"}
    if row.get("description_unknown") == "1":
        desc_cell = {"value": desc, "color": "gray"}
    if row.get("category_unknown") == "1":
        category_cell = {"value": category, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "category": category_cell,
        "name": name_cell,
        "description": desc_cell,
    }


def _normalize_transform_row(row: Dict[str, str]) -> Dict[str, object]:
    spec = row.get("spec", "")
    spec_cell: object = spec
    if row.get("spec_unknown") == "1":
        spec_cell = {"value": spec, "color": "gray"}
    return {
        "file": row.get("file", ""),
        "spec": spec_cell,
    }


def cmd_add(args: argparse.Namespace) -> int:
    installed = addon_app.add(args.filename, root=args.root)
    logger.info("Installed %d file(s).", len(installed))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = addon_app.list_installed(root=args.root)
    width = config_core.output_width(root=args.root)
    rules = data["rules"]
    columns = ("file", "category", "name", "description")
    transform_columns = ("file", "spec")
    spec_rows = [_normalize_row(row) for row in data["specs"]]
    rules_rows = [_normalize_row(row) for row in rules]
    transform_rows = [_normalize_transform_row(row) for row in data["transforms"]]
    category_order = {"info_spec": 0, "metadata_spec": 1, "converter_entrypoint": 2, "<Unknown>": 9}
    spec_rows.sort(
        key=lambda row: (
            category_order.get(str(row.get("category", "")), 9),
            str(row.get("name", "")),
        )
    )
    rules_rows.sort(
        key=lambda row: (
            category_order.get(str(row.get("category", "")), 9),
            str(row.get("name", "")),
        )
    )
    spec_widths = formatter.compute_column_widths(columns, spec_rows)
    rules_widths = formatter.compute_column_widths(columns, rules_rows)
    col_widths = {
        col: max(spec_widths.get(col, 0), rules_widths.get(col, 0))
        for col in columns[:-1]
    }
    spec_table = formatter.format_table(
        "Specs",
        columns,
        spec_rows,
        width=width,
        colors={"file": "gray", "name": "cyan", "description": "gray"},
        title_color="cyan",
        col_widths=col_widths,
    )
    rules_table = formatter.format_table(
        "Rules",
        columns,
        rules_rows,
        width=width,
        colors={"file": "gray", "name": "yellow", "description": "gray"},
        title_color="yellow",
        col_widths=col_widths,
    )
    transforms_table = formatter.format_table(
        "Transforms",
        transform_columns,
        transform_rows,
        width=width,
        colors={"file": "gray", "spec": "cyan"},
        title_color="cyan",
    )
    logger.info("%s", rules_table)
    logger.info("")
    logger.info("%s", spec_table)
    if transform_rows:
        logger.info("")
        logger.info("%s", transforms_table)
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    try:
        removed = addon_app.remove(
            args.filename,
            root=args.root,
            kind=args.kind,
            force=args.force,
        )
    except FileNotFoundError as exc:
        logger.error("No matching addon files found: %s", exc)
        return 2
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2
    logger.info("Removed %d file(s).", len(removed))
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
    addon_parser = subparsers.add_parser(
        "addon",
        help="Manage info specs and rules.",
    )
    addon_parser.add_argument(
        "--root",
        help="Override config root directory (default: BRKRAW_CONFIG_HOME or ~/.brkraw).",
    )
    addon_parser.set_defaults(func=cmd_addon, parser=addon_parser)
    addon_sub = addon_parser.add_subparsers(dest="addon_command")

    add_parser = addon_sub.add_parser("add", help="Install a spec or rule file.")
    add_parser.add_argument("filename", help="Spec/rule YAML.")
    add_parser.set_defaults(addon_func=cmd_add)

    list_parser = addon_sub.add_parser("list", help="List installed specs and rules.")
    list_parser.set_defaults(addon_func=cmd_list)

    rm_parser = addon_sub.add_parser("rm", help="Remove an installed spec or rule file.")
    rm_parser.add_argument("filename", help="Spec/rule filename to remove.")
    rm_parser.add_argument(
        "--kind",
        choices=["spec", "rule", "transform"],
        help="Limit removal to a specific kind.",
    )
    rm_parser.add_argument(
        "--force",
        action="store_true",
        help="Remove even if dependencies are detected.",
    )
    rm_parser.set_defaults(addon_func=cmd_rm)
