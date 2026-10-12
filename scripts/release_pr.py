#!/usr/bin/env python3
"""Open the upstream release PR from the fork branch ``release/<version>``.

Steps, in order (each stops the run if it fails):

1. Local checks: the branch is ``release/<version>``, the tree is clean, the
   ``--repo`` you name is the ``upstream`` remote and differs from ``origin``.
2. Refresh ``docs/dev/contributors.md`` from the GitHub API (read only;
   ``--skip-contributors`` to skip).
3. ``release_prep.py``: version files, notes heading (hand-written text kept).
4. ``pytest -q tests`` (``--skip-tests`` to skip).
5. One commit with the named files.
6. ``git push --no-follow-tags origin HEAD:refs/heads/release/<version>``:
   the branch only, never a tag.
7. ``gh pr create --repo <repo>`` (or reuse the open PR) and
   ``gh pr edit --add-label release`` (rc included; the label is what lets
   ``Release On Merge`` tag the merge commit upstream).

It never creates or pushes a tag and never merges. ``--dry-run`` prints every
step and runs only read-only local Git commands (``rev-parse``, ``status``,
``remote get-url``): no file is written and nothing uses the network.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTORS_REL = "docs/dev/contributors.md"
RELEASE_LABEL = "release"


class ReleasePRError(Exception):
    pass


def _load_prep(root: Path):
    path = root / "scripts" / "release_prep.py"
    spec = importlib.util.spec_from_file_location("_brkraw_release_prep", path)
    if spec is None or spec.loader is None:
        raise ReleasePRError(f"Cannot load {path}.")
    module = importlib.util.module_from_spec(spec)
    old_flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ in the tree, also in --dry-run
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_flag
    return module


def _run(cmd: Sequence[str], root: Path, *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(list(cmd), cwd=root, text=True, capture_output=True)
    if check and result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        raise ReleasePRError(f"{shlex.join(cmd)} failed: {msg}")
    return result


def _git_read(root: Path, *args: str) -> str:
    """Read-only local Git commands only; used in dry-run too."""
    assert args[0] in ("rev-parse", "status", "remote"), args
    return _run(["git", *args], root).stdout.strip()


def parse_owner_repo(remote_url: str) -> str:
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", remote_url.strip())
    if not match:
        raise ReleasePRError(f"Cannot read owner/repo from remote URL {remote_url!r}.")
    return f"{match.group(1)}/{match.group(2)}"


def check_state(root: Path, version: str, repo: str, remote_upstream: str, remote_origin: str) -> Tuple[str, str]:
    """Return (branch, fork owner). Raises ReleasePRError when anything does not match."""
    branch = _git_read(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != f"release/{version}":
        raise ReleasePRError(f"Run this on branch release/{version}; the current branch is {branch!r}.")
    upstream = parse_owner_repo(_git_read(root, "remote", "get-url", remote_upstream))
    origin = parse_owner_repo(_git_read(root, "remote", "get-url", remote_origin))
    if upstream.lower() != repo.lower():
        raise ReleasePRError(
            f"--repo {repo} does not match remote {remote_upstream!r} ({upstream}); nothing was done."
        )
    if origin.lower() == upstream.lower():
        raise ReleasePRError(
            f"Remote {remote_origin!r} and {remote_upstream!r} are the same repository ({origin}); "
            "the release branch must come from the fork."
        )
    return branch, origin.split("/", 1)[0]


def pr_body(version: str, files: List[str]) -> str:
    listed = "\n".join(f"- `{f}`" for f in files) or "- (none)"
    return (
        f"## Release v{version}\n\n"
        "Version bump and release-note heading for this release. The release notes\n"
        "(`RELEASE_NOTES.md`) are written by hand in the feature PRs; this PR only\n"
        "renames their `Unreleased` section.\n\n"
        f"### Files updated\n{listed}\n\n"
        "### Before merging\n"
        "- [ ] CI passes\n"
        "- [ ] Release notes read correctly (they become the GitHub release text)\n"
        f"- [ ] The `{RELEASE_LABEL}` label is on this PR\n"
        "- [ ] Merge with a merge commit (not squash or rebase); `Release On Merge`\n"
        "      then tags the merge commit and starts `Create Release`\n"
    )


def main(argv: Optional[List[str]] = None, root: Optional[Path] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="Release version, e.g. 0.6.1 (no leading v)")
    parser.add_argument("--repo", required=True, help="Upstream repository OWNER/NAME, e.g. BrkRaw/brkraw")
    parser.add_argument("--base", default="main", help="Upstream base branch (default: main)")
    parser.add_argument("--remote-upstream", default="upstream", help="Remote name of --repo (default: upstream)")
    parser.add_argument("--remote-origin", default="origin", help="Remote name of the fork (default: origin)")
    parser.add_argument("--title", default=None, help="PR title (default: Release v<version>)")
    parser.add_argument("--date", default=None, help="Release-note date (default: today)")
    parser.add_argument("--skip-tests", action="store_true", help="Do not run pytest -q tests before the commit")
    parser.add_argument("--skip-contributors", action="store_true", help="Do not refresh docs/dev/contributors.md")
    parser.add_argument("--dry-run", action="store_true", help="Print every step; write nothing, no network")
    args = parser.parse_args(argv)
    root = root or REPO_ROOT

    try:
        return _main(args, root)
    except ReleasePRError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _main(args: argparse.Namespace, root: Path) -> int:
    import datetime as dt

    prep = _load_prep(root)
    try:
        prep.parse_version(args.version)
    except prep.ReleasePrepError as exc:
        raise ReleasePRError(str(exc))
    branch, fork_owner = check_state(root, args.version, args.repo, args.remote_upstream, args.remote_origin)

    dirty = _git_read(root, "status", "--porcelain")
    if dirty and not args.dry_run:
        raise ReleasePRError("The working tree is not clean. Commit or stash first.")
    if dirty:
        print("warning: the working tree is not clean (dry-run continues).")

    date = args.date or dt.date.today().isoformat()
    try:
        _previous, changes, messages = prep.plan_release(root, args.version, date=date)
    except prep.ReleasePrepError as exc:
        raise ReleasePRError(f"{exc} Nothing was written.")
    for message in messages:
        print(message)

    title = args.title or f"Release v{args.version}"
    head = f"{fork_owner}:{branch}"
    files = list(changes)
    py = sys.executable
    contributors_cmd = [
        py, "scripts/update_contributors.py", "--source", "github", "--repo", args.repo,
        "--output", CONTRIBUTORS_REL,
    ]
    test_cmd = [py, "-m", "pytest", "-q", "tests"]
    push_cmd = ["git", "push", "--no-follow-tags", args.remote_origin, f"HEAD:refs/heads/{branch}"]
    list_cmd = [
        "gh", "pr", "list", "--repo", args.repo, "--head", branch, "--state", "open",
        "--json", "number", "--jq", ".[0].number",
    ]

    def create_cmd(body: str) -> List[str]:
        return [
            "gh", "pr", "create", "--repo", args.repo, "--base", args.base, "--head", head,
            "--title", title, "--body", body,
        ]

    def label_cmd(number: str) -> List[str]:
        return ["gh", "pr", "edit", number, "--repo", args.repo, "--add-label", RELEASE_LABEL]

    if args.dry_run:
        say = lambda cmd: print("[dry-run] would run: " + shlex.join(cmd))  # noqa: E731
        print(f"[dry-run] branch {branch}, fork {fork_owner}, upstream {args.repo}, base {args.base}")
        if not args.skip_contributors:
            say(contributors_cmd)
        print(f"[dry-run] would update {len(files)} file(s): {', '.join(files)}")
        if not args.skip_tests:
            say(test_cmd)
        say(["git", "add", "--", *files, "(+ " + CONTRIBUTORS_REL + " if changed)"])
        say(["git", "commit", "-m", f"Prepare release v{args.version}", "--", "..."])
        say(push_cmd)
        say(list_cmd)
        say(create_cmd("<release PR body>"))
        say(label_cmd("<PR number>"))
        print("[dry-run] no tag is created or pushed; Release On Merge tags the merge commit upstream.")
        return 0

    if not args.skip_contributors:
        _run(contributors_cmd, root)
        if _run(["git", "diff", "--name-only", "--", CONTRIBUTORS_REL], root).stdout.strip():
            files.append(CONTRIBUTORS_REL)

    for rel, (_old, new) in changes.items():
        (root / rel).write_text(new, encoding="utf-8")
    print(f"Updated: {', '.join(changes)}")

    if not args.skip_tests:
        result = subprocess.run(test_cmd, cwd=root, text=True)
        if result.returncode != 0:
            raise ReleasePRError(
                "Tests failed; nothing was committed or pushed. The changed files are left for you to "
                "inspect; undo with: git restore -- " + " ".join(shlex.quote(f) for f in files)
            )

    _run(["git", "add", "--", *files], root)
    _run(["git", "commit", "-m", f"Prepare release v{args.version}", "--", *files], root)
    _run(push_cmd, root)
    print(f"Pushed {branch} to {args.remote_origin} (no tags).")

    number = _run(list_cmd, root).stdout.strip()
    if number and number != "null":
        print(f"Using the open PR #{number}.")
    else:
        url = _run(create_cmd(pr_body(args.version, files)), root).stdout.strip()
        match = re.search(r"/pull/(\d+)", url)
        if not match:
            raise ReleasePRError(f"gh pr create did not return a PR URL: {url!r}")
        number = match.group(1)
        print(f"Opened {url}")
    _run(label_cmd(number), root)
    print(f"Added label '{RELEASE_LABEL}' to #{number}.")
    print(
        "Next (by hand): check CI with "
        f"`gh pr checks {number} --repo {args.repo}`, then merge with a merge commit: "
        f"`gh pr merge {number} --repo {args.repo} --merge`."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
