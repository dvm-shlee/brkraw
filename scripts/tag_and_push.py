#!/usr/bin/env python3
"""Retired: release tags are made only by the upstream workflow.

``Release On Merge`` (``.github/workflows/release_on_merge.yml``) tags the merge
commit of a release PR that carries the ``release`` label and starts
``Create Release``. A tag pushed by hand would not start a release
(``release.yml`` has no tag-push trigger) and could point at another commit
than the one the workflow tags. This script therefore changes nothing and
prints the supported recovery command instead.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = REPO_ROOT / "src" / "brkraw" / "__init__.py"


def get_version() -> str:
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", INIT_PATH.read_text(encoding="utf-8"))
    return match.group(1) if match else "<version>"


def main() -> int:
    version = get_version()
    print(
        "tag_and_push.py no longer creates or pushes tags.\n"
        "Release tags are made by the upstream workflow when a PR with the 'release'\n"
        "label is merged with a merge commit.\n"
        "If that workflow skipped the tag (no label, or no PR found for the merge\n"
        "commit) and nothing else was merged since, start it by hand:\n"
        f"  gh workflow run release_on_merge.yml --repo BrkRaw/brkraw -f tag={version} -f run_release=true\n"
        "If the tag exists but the release failed:\n"
        f"  gh workflow run release.yml --repo BrkRaw/brkraw -f tag={version}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
