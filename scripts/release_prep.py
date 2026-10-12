#!/usr/bin/env python3
"""Prepare a release locally: bump the version files, keep the release notes.

What it changes (and nothing else):

- ``src/brkraw/__init__.py``: ``__version__``
- ``README.md``: ``BrkRaw (vX)`` and the BibTeX block made from CITATION.cff
- ``CITATION.cff``: ``version:``
- ``pyproject.toml``: the ``Development Status`` classifier
- ``docs/index.md``: the "current pre-release / current release" line
- ``RELEASE_NOTES.md``: only the first heading (``# Release vX``), the
  ``Date:`` line and a ``## Unreleased`` heading, which becomes
  ``## Changes since <previous version>``. The hand-written text is kept
  line for line.

It runs no Git command and uses no network. Every check runs before the
first file is written, so a refused run leaves the tree unchanged.
``--dry-run`` prints the changes as a diff and writes nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

INIT_REL = "src/brkraw/__init__.py"
README_REL = "README.md"
CITATION_REL = "CITATION.cff"
PYPROJECT_REL = "pyproject.toml"
DOCS_INDEX_REL = "docs/index.md"
NOTES_REL = "RELEASE_NOTES.md"

# brkraw versions: X.Y.Z or X.Y.Z{a,b,rc}N, no leading "v" (tags use the same text).
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")
VERSION_LINE_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]\s*$", re.MULTILINE)
DOCS_LINE_RE = re.compile(
    r"This documentation describes brkraw \d+\.\d+ \(current (?:pre-release|release): [^)]+\)\."
)


class ReleasePrepError(Exception):
    pass


def parse_version(version: str) -> Tuple[str, Optional[str]]:
    """Return (major.minor, pre-release kind or None); refuse other forms."""
    match = VERSION_RE.match(version)
    if not match:
        raise ReleasePrepError(
            f"Version {version!r} is not X.Y.Z or X.Y.Z(a|b|rc)N (no leading 'v')."
        )
    return f"{match.group(1)}.{match.group(2)}", match.group(4)


def development_status(version: str) -> str:
    _, pre = parse_version(version)
    if pre == "a":
        return "3 - Alpha"
    if pre in ("b", "rc"):
        return "4 - Beta"
    return "5 - Production/Stable"


def read_version(init_text: str) -> str:
    match = VERSION_LINE_RE.search(init_text)
    if not match:
        raise ReleasePrepError(f"No __version__ line in {INIT_REL}.")
    return match.group(1)


def _sub_once(pattern: str, repl: str, text: str, what: str, flags: int = 0) -> str:
    new_text, count = re.subn(pattern, lambda _m: repl, text, count=1, flags=flags)
    if count != 1:
        raise ReleasePrepError(f"Could not find {what}.")
    return new_text


def update_init(text: str, version: str) -> str:
    return _sub_once(
        r"^__version__\s*=\s*['\"][^'\"]+['\"]\s*$",
        f"__version__ = '{version}'",
        text,
        f"__version__ in {INIT_REL}",
        flags=re.MULTILINE,
    )


def update_citation(text: str, version: str) -> str:
    return _sub_once(
        r"^version:\s*\"?[0-9A-Za-z.\-]+\"?\s*$",
        f'version: "{version}"',
        text,
        f"version: in {CITATION_REL}",
        flags=re.MULTILINE,
    )


def update_pyproject(text: str, version: str) -> str:
    return _sub_once(
        r"^\s*[\"']Development Status :: [^\"']+[\"'],?\s*$",
        f"    'Development Status :: {development_status(version)}',",
        text,
        f"the Development Status classifier in {PYPROJECT_REL}",
        flags=re.MULTILINE,
    )


def update_docs_index(text: str, version: str) -> str:
    major_minor, pre = parse_version(version)
    kind = "pre-release" if pre else "release"
    return _sub_once(
        DOCS_LINE_RE.pattern,
        f"This documentation describes brkraw {major_minor} (current {kind}: {version}).",
        text,
        f"the 'This documentation describes brkraw ...' line in {DOCS_INDEX_REL}",
    )


def _load_bibtex_module(root: Path):
    path = root / "scripts" / "update_readme_bibtex.py"
    spec = importlib.util.spec_from_file_location("_brkraw_update_readme_bibtex", path)
    if spec is None or spec.loader is None:
        raise ReleasePrepError(f"Cannot load {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def update_readme(text: str, version: str, citation_text: str, root: Path) -> str:
    text = _sub_once(
        r"BrkRaw\s+\(v[0-9A-Za-z.\-]+\)", f"BrkRaw (v{version})", text, f"'BrkRaw (vX)' in {README_REL}"
    )
    import yaml  # brkraw runtime dependency

    bib = _load_bibtex_module(root)
    cff = yaml.safe_load(citation_text)
    if not isinstance(cff, dict):
        raise ReleasePrepError(f"{CITATION_REL} is not a mapping.")
    block = f"{bib.BEGIN}\n```biblatex\n{bib.cff_to_biblatex(cff)}```\n{bib.END}"
    pattern = re.escape(bib.BEGIN) + r".*?" + re.escape(bib.END)
    new_text, count = re.subn(pattern, lambda _m: block, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise ReleasePrepError(f"Could not find the BibTeX block markers in {README_REL}.")
    return new_text


def update_release_notes(text: str, version: str, previous: str, date: str) -> str:
    """Change only the first heading, the Date line and a '## Unreleased' heading."""
    lines = text.splitlines(keepends=True)
    if not lines or not re.match(r"^# Release v\S+\s*$", lines[0]):
        raise ReleasePrepError(
            f"{NOTES_REL} must start with a '# Release vX' heading; nothing was changed."
        )
    lines[0] = f"# Release v{version}\n"

    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    for i in range(1, first_section):
        if lines[i].startswith("Date:"):
            lines[i] = f"Date: {date}\n"
            break

    unreleased = [i for i, line in enumerate(lines) if re.match(r"^## Unreleased\s*$", line, re.IGNORECASE)]
    if len(unreleased) > 1:
        raise ReleasePrepError(f"{NOTES_REL} has more than one '## Unreleased' heading.")
    for i in unreleased:
        lines[i] = f"## Changes since {previous}\n"
    return "".join(lines)


def plan_release(
    root: Path, version: str, *, date: str, docs_index: bool = True
) -> Tuple[str, Dict[str, Tuple[str, str]], List[str]]:
    """Compute every change in memory. Returns (previous version, {rel: (old, new)}, notes)."""
    parse_version(version)
    messages: List[str] = []

    def read(rel: str) -> str:
        path = root / rel
        if not path.is_file():
            raise ReleasePrepError(f"Missing {rel}.")
        return path.read_text(encoding="utf-8")

    old = {rel: read(rel) for rel in (INIT_REL, README_REL, CITATION_REL, PYPROJECT_REL, NOTES_REL)}
    previous = read_version(old[INIT_REL])
    if previous == version:
        raise ReleasePrepError(f"The version is already {version}.")

    new = {
        INIT_REL: update_init(old[INIT_REL], version),
        CITATION_REL: update_citation(old[CITATION_REL], version),
        PYPROJECT_REL: update_pyproject(old[PYPROJECT_REL], version),
        NOTES_REL: update_release_notes(old[NOTES_REL], version, previous, date),
    }
    new[README_REL] = update_readme(old[README_REL], version, new[CITATION_REL], root)
    if not re.search(r"^## Unreleased\s*$", old[NOTES_REL], re.MULTILINE | re.IGNORECASE):
        messages.append(f"Note: {NOTES_REL} has no '## Unreleased' section; only its heading and date change.")

    if docs_index:
        old[DOCS_INDEX_REL] = read(DOCS_INDEX_REL)
        try:
            new[DOCS_INDEX_REL] = update_docs_index(old[DOCS_INDEX_REL], version)
        except ReleasePrepError as exc:
            messages.append(f"Note: {exc} {DOCS_INDEX_REL} left unchanged.")
            new[DOCS_INDEX_REL] = old[DOCS_INDEX_REL]

    changes = {rel: (old[rel], new[rel]) for rel in new if new[rel] != old[rel]}
    return previous, changes, messages


def main(argv: Optional[List[str]] = None, root: Optional[Path] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="Release version, e.g. 0.6.1 or 0.6.1rc3 (no leading v)")
    parser.add_argument("--date", default=None, help="Date for the release notes (default: today, YYYY-MM-DD)")
    parser.add_argument("--skip-docs-index", action="store_true", help="Leave docs/index.md unchanged")
    parser.add_argument("--dry-run", action="store_true", help="Print the changes as a diff; write nothing")
    args = parser.parse_args(argv)
    root = root or REPO_ROOT
    date = args.date or dt.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        print(f"error: --date must be YYYY-MM-DD, got {date!r}", file=sys.stderr)
        return 2

    try:
        previous, changes, messages = plan_release(
            root, args.version, date=date, docs_index=not args.skip_docs_index
        )
    except ReleasePrepError as exc:
        print(f"error: {exc} Nothing was written.", file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    if args.dry_run:
        print(f"[dry-run] {previous} -> {args.version}; would update {len(changes)} file(s):")
        for rel, (old_text, new_text) in changes.items():
            sys.stdout.writelines(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                    n=0,
                )
            )
        return 0

    for rel, (_old_text, new_text) in changes.items():
        (root / rel).write_text(new_text, encoding="utf-8")
    print(f"{previous} -> {args.version}")
    for rel in changes:
        print(f"Updated {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
