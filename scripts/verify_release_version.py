#!/usr/bin/env python3
"""Check that a release tag is exactly the package version.

Used by the release workflows before tagging, releasing and publishing:
the tag must be X.Y.Z or X.Y.Z(a|b|rc)N, with no leading "v", and equal to
``__version__`` in ``src/brkraw/__init__.py`` of the checked-out commit.
Exit 0 when they match, 1 otherwise. The tag comes from ``--tag`` or the
``TAG`` environment variable.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_REL = "src/brkraw/__init__.py"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$")


def check(tag: str, root: Path) -> Optional[str]:
    """Return None when the tag matches, otherwise the reason."""
    if not VERSION_RE.match(tag):
        return f"tag {tag!r} is not X.Y.Z or X.Y.Z(a|b|rc)N without a leading 'v'"
    text = (root / INIT_REL).read_text(encoding="utf-8").lstrip("﻿")
    match = re.search(r"^__version__(?:\s*:\s*[^=]+)?\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
    if not match:
        return f"no __version__ in {INIT_REL}"
    if match.group(1) != tag:
        return f"tag {tag!r} does not match __version__ {match.group(1)!r} in {INIT_REL}"
    return None


def main(argv: Optional[List[str]] = None, root: Optional[Path] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default=os.environ.get("TAG", ""), help="Tag to check (default: $TAG)")
    args = parser.parse_args(argv)
    reason = check(args.tag.strip(), root or REPO_ROOT)
    if reason:
        print(f"Release version check failed: {reason}.", file=sys.stderr)
        return 1
    print(f"Release version check passed: {args.tag.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
