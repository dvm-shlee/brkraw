"""Release tools: hand-written notes are kept, --dry-run changes nothing and
uses no network, tags are only made by the upstream workflow.

The scripts are copied into a synthetic repository under tmp_path and run
there as separate processes, with `git` and `gh` replaced on PATH by small
recorders. Commands that would reach the network (`fetch`, `push`,
`ls-remote`, `pull`, `clone`) are recorded and never executed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

NEW_RC = "9.9.9rc1"
NEW_FINAL = "9.9.9"

NETWORK_GIT = {"fetch", "push", "ls-remote", "pull", "clone"}
CHANGING_GIT = {"add", "commit", "tag", "checkout", "switch", "reset", "merge", "rebase", "stash", "restore", "rm", "mv"}

REAL_GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(REAL_GIT is None, reason="git is not installed")


def current_version() -> str:
    text = (REPO_ROOT / "src" / "brkraw" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", text)
    assert match
    return match.group(1)


def notes_text(version: str) -> str:
    return (
        f"# Release v{version}\n"
        "\n"
        "Date: 2026-01-01\n"
        "Changes since 0.5.7\n"
        "\n"
        "Intro written by hand. It must survive the release prep.\n"
        "\n"
        "## Unreleased\n"
        "\n"
        "- Hand-written entry one.\n"
        "- Hand-written entry two, with `code` and a [link](docs/x.md).\n"
        "\n"
        "## Changes since 0.6.1rc1\n"
        "\n"
        "- An older entry.\n"
        "\n"
        "## Highlights\n"
        "\n"
        + "".join(f"- Highlight line {i}.\n" for i in range(40))
    )


# --- synthetic repository ---------------------------------------------------


def _write_exe(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


FAKE_GIT = r'''
import json, os, sys
LOG = os.environ["FAKE_LOG_DIR"] + "/git.jsonl"
REAL = os.environ["FAKE_REAL_GIT"]
NETWORK = {"fetch", "push", "ls-remote", "pull", "clone"}
args = sys.argv[1:]
i = 0
while i < len(args) and args[i].startswith("-"):
    i += 2 if args[i] in ("-C", "-c") else 1
sub = args[i] if i < len(args) else ""
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")
if sub in NETWORK:
    sys.exit(0 if sub == "push" else 1)
os.execv(REAL, [REAL] + args)
'''

FAKE_GH = r'''
import json, os, sys
LOG = os.environ["FAKE_LOG_DIR"] + "/gh.jsonl"
args = sys.argv[1:]
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")
if os.environ.get("FAKE_GH_MODE") != "ok":
    sys.exit(1)
if args[:2] == ["pr", "list"]:
    print("")
elif args[:2] == ["pr", "create"]:
    print("https://github.com/BrkRaw/brkraw/pull/999")
sys.exit(0)
'''


class Sandbox:
    def __init__(self, root: Path, logs: Path, env: dict):
        self.root = root
        self.logs = logs
        self.env = env

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / script), *args],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=300,
        )

    def git(self, *args: str) -> str:
        out = subprocess.run(
            [REAL_GIT, *args], cwd=self.root, env=self.env, text=True, capture_output=True, check=True
        )
        return out.stdout

    def calls(self, name: str) -> list:
        path = self.logs / f"{name}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def git_subcommands(self) -> list:
        subs = []
        for args in self.calls("git"):
            i = 0
            while i < len(args) and args[i].startswith("-"):
                i += 2 if args[i] in ("-C", "-c") else 1
            subs.append(args[i] if i < len(args) else "")
        return subs

    def snapshot(self) -> dict:
        files = {}
        # .git/ is left out: read-only `git status` may refresh the index file.
        # __pycache__ is included: a dry run must not leave bytecode either.
        for path in sorted(self.root.rglob("*")):
            rel_parts = path.relative_to(self.root).parts
            if path.is_file() and rel_parts[0] != ".git":
                files[str(path.relative_to(self.root))] = path.read_bytes()
        return files


@pytest.fixture()
def sandbox(tmp_path: Path) -> Sandbox:
    root = tmp_path / "repo"
    for rel in (
        ".gitignore",
        "README.md",
        "CITATION.cff",
        "pyproject.toml",
        "src/brkraw/__init__.py",
        "docs/index.md",
        "docs/dev/contributors.md",
    ):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, dest)
    (root / "scripts").mkdir()
    for script in SCRIPTS.glob("*.py"):
        shutil.copyfile(script, root / "scripts" / script.name)
    (root / "RELEASE_NOTES.md").write_text(notes_text(current_version()), encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_exe(bin_dir / "git", FAKE_GIT)
    _write_exe(bin_dir / "gh", FAKE_GH)
    logs = tmp_path / "logs"
    logs.mkdir()

    env = dict(os.environ)
    env.update(
        {
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
            "FAKE_LOG_DIR": str(logs),
            "FAKE_REAL_GIT": REAL_GIT,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            # Any HTTP(S) call from a script (urllib honours these) goes to a
            # closed local port and fails, so a network call shows as an error.
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        }
    )
    for key in ("FAKE_GH_MODE", "NO_PROXY", "no_proxy"):
        env.pop(key, None)
    box = Sandbox(root, logs, env)
    box.git("init", "-q")
    box.git("config", "user.name", "Release Test")
    box.git("config", "user.email", "release-test@example.invalid")
    box.git("config", "commit.gpgsign", "false")
    box.git("remote", "add", "origin", "git@github.com:dvm-shlee/brkraw.git")
    box.git("remote", "add", "upstream", "git@github.com:BrkRaw/brkraw.git")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "initial")
    box.git("checkout", "-q", "-b", f"release/{NEW_RC}")
    for path in logs.iterdir():
        path.unlink()
    return box


def changed_lines(before: str, after: str) -> list:
    a = before.splitlines()
    b = after.splitlines()
    assert len(a) == len(b), "line count changed"
    return [(x, y) for x, y in zip(a, b) if x != y]


# --- release_prep.py ---------------------------------------------------------


def test_release_prep_keeps_hand_written_notes(sandbox: Sandbox) -> None:
    old = current_version()
    before = (sandbox.root / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    result = sandbox.run("release_prep.py", "--version", NEW_RC, "--date", "2030-01-02")
    assert result.returncode == 0, result.stderr

    after = (sandbox.root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert changed_lines(before, after) == [
        (f"# Release v{old}", f"# Release v{NEW_RC}"),
        ("Date: 2026-01-01", "Date: 2030-01-02"),
        ("## Unreleased", f"## Changes since {old}"),
    ]


def test_release_prep_accepts_the_repository_notes(sandbox: Sandbox) -> None:
    old = current_version()
    real = (REPO_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    (sandbox.root / "RELEASE_NOTES.md").write_text(real, encoding="utf-8")

    result = sandbox.run("release_prep.py", "--version", NEW_RC, "--date", "2030-01-02")
    assert result.returncode == 0, result.stderr

    after = (sandbox.root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    changed = changed_lines(real, after)
    assert changed[0] == (real.splitlines()[0], f"# Release v{NEW_RC}")
    assert all(new.startswith("Date: 2030-01-02") or new == f"## Changes since {old}" for _, new in changed[1:])
    assert len(changed) <= 3


def test_release_prep_updates_every_version_file(sandbox: Sandbox) -> None:
    result = sandbox.run("release_prep.py", "--version", NEW_RC, "--date", "2030-01-02")
    assert result.returncode == 0, result.stderr
    root = sandbox.root
    assert f"__version__ = '{NEW_RC}'" in (root / "src/brkraw/__init__.py").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"BrkRaw (v{NEW_RC})" in readme
    assert f"version = {{{NEW_RC}}}" in readme  # BibTeX block follows CITATION.cff
    assert f'version: "{NEW_RC}"' in (root / "CITATION.cff").read_text(encoding="utf-8")
    assert "Development Status :: 4 - Beta" in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert f"brkraw 9.9 (current pre-release: {NEW_RC})" in (root / "docs/index.md").read_text(encoding="utf-8")
    # pyproject.toml is not listed: an rc stays "4 - Beta", so that file does not change.
    for rel in ("src/brkraw/__init__.py", "README.md", "CITATION.cff", "docs/index.md", "RELEASE_NOTES.md"):
        assert f"Updated {rel}" in result.stdout, f"{rel} not reported as updated"


def test_release_prep_final_version(sandbox: Sandbox) -> None:
    result = sandbox.run("release_prep.py", "--version", NEW_FINAL, "--date", "2030-01-02")
    assert result.returncode == 0, result.stderr
    root = sandbox.root
    assert "Development Status :: 5 - Production/Stable" in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "Updated pyproject.toml" in result.stdout
    assert f"brkraw 9.9 (current release: {NEW_FINAL})" in (root / "docs/index.md").read_text(encoding="utf-8")


def test_release_prep_dry_run_writes_nothing(sandbox: Sandbox) -> None:
    before = sandbox.snapshot()
    result = sandbox.run("release_prep.py", "--version", NEW_RC, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert sandbox.snapshot() == before
    assert f"+# Release v{NEW_RC}" in result.stdout


@pytest.mark.parametrize("bad", ["v9.9.9", "9.9", "9.9.9-rc1", "9.9.9.post1", "CURRENT"])
def test_release_prep_refuses_bad_version_and_writes_nothing(sandbox: Sandbox, bad: str) -> None:
    if bad == "CURRENT":
        bad = current_version()
    before = sandbox.snapshot()
    result = sandbox.run("release_prep.py", "--version", bad)
    assert result.returncode != 0
    assert sandbox.snapshot() == before


def test_release_prep_refuses_notes_without_release_heading(sandbox: Sandbox) -> None:
    notes = sandbox.root / "RELEASE_NOTES.md"
    notes.write_text("Some notes without the heading\n", encoding="utf-8")
    before = sandbox.snapshot()
    result = sandbox.run("release_prep.py", "--version", NEW_RC)
    assert result.returncode != 0
    assert sandbox.snapshot() == before


def test_release_prep_runs_no_git(sandbox: Sandbox) -> None:
    result = sandbox.run("release_prep.py", "--version", NEW_RC)
    assert result.returncode == 0, result.stderr
    assert sandbox.calls("git") == []
    assert sandbox.calls("gh") == []


# --- release_pr.py -----------------------------------------------------------


def test_release_pr_dry_run_changes_nothing_and_uses_no_network(sandbox: Sandbox) -> None:
    before = sandbox.snapshot()
    result = sandbox.run("release_pr.py", "--dry-run", "--repo", "BrkRaw/brkraw", "--version", NEW_RC)
    assert result.returncode == 0, result.stderr + result.stdout
    assert sandbox.snapshot() == before
    assert sandbox.git("status", "--porcelain") == ""
    assert sandbox.calls("gh") == []
    used = set(sandbox.git_subcommands())
    assert not used & NETWORK_GIT, used
    assert not used & CHANGING_GIT, used
    out = result.stdout
    assert f"push --no-follow-tags origin HEAD:refs/heads/release/{NEW_RC}" in out
    assert "--repo BrkRaw/brkraw" in out
    assert "--add-label release" in out


def test_release_pr_pushes_branch_only_and_labels_rc(sandbox: Sandbox) -> None:
    sandbox.env["FAKE_GH_MODE"] = "ok"
    head_before = sandbox.git("rev-parse", "HEAD").strip()
    notes_before = (sandbox.root / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    result = sandbox.run(
        "release_pr.py", "--repo", "BrkRaw/brkraw", "--version", NEW_RC, "--skip-contributors"
    )
    assert result.returncode == 0, result.stderr + result.stdout

    pushes = [args for args in sandbox.calls("git") if "push" in args]
    assert pushes == [["push", "--no-follow-tags", "origin", f"HEAD:refs/heads/release/{NEW_RC}"]]
    for args in sandbox.calls("git"):
        assert "--tags" not in args and "--follow-tags" not in args
        assert not any(a.startswith("refs/tags") for a in args)
    assert "tag" not in sandbox.git_subcommands()

    gh = sandbox.calls("gh")
    assert gh, "no PR command ran"
    for args in gh:
        assert "--repo" in args and args[args.index("--repo") + 1] == "BrkRaw/brkraw", args
    assert any(a[:2] == ["pr", "create"] and "dvm-shlee:release/" + NEW_RC in a for a in gh)
    assert any(a[:3] == ["pr", "edit", "999"] and "release" in a for a in gh)

    assert sandbox.git("rev-parse", "HEAD~1").strip() == head_before
    assert sandbox.git("status", "--porcelain") == ""
    notes_after = (sandbox.root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert len(changed_lines(notes_before, notes_after)) == 3


def test_release_pr_failing_tests_stop_before_commit(sandbox: Sandbox) -> None:
    sandbox.env["FAKE_GH_MODE"] = "ok"
    (sandbox.root / "tests" / "test_fail.py").write_text("def test_fail():\n    assert False\n", encoding="utf-8")
    sandbox.git("add", "tests/test_fail.py")
    sandbox.git("commit", "-q", "-m", "a failing test")
    head_before = sandbox.git("rev-parse", "HEAD").strip()

    result = sandbox.run(
        "release_pr.py", "--repo", "BrkRaw/brkraw", "--version", NEW_RC, "--skip-contributors"
    )
    assert result.returncode != 0
    assert sandbox.git("rev-parse", "HEAD").strip() == head_before
    assert "push" not in sandbox.git_subcommands()
    assert sandbox.calls("gh") == []


@pytest.mark.parametrize(
    "args",
    [
        ("--repo", "Someone/else"),  # does not match the upstream remote
        ("--repo", "BrkRaw/brkraw", "--remote-upstream", "origin"),  # fork as upstream
    ],
)
def test_release_pr_refuses_wrong_repo(sandbox: Sandbox, args: tuple) -> None:
    before = sandbox.snapshot()
    result = sandbox.run("release_pr.py", "--dry-run", *args, "--version", NEW_RC)
    assert result.returncode != 0
    assert sandbox.snapshot() == before


def test_release_pr_refuses_branch_not_named_for_version(sandbox: Sandbox) -> None:
    sandbox.git("checkout", "-q", "-b", "feat/something")
    result = sandbox.run("release_pr.py", "--dry-run", "--repo", "BrkRaw/brkraw", "--version", NEW_RC)
    assert result.returncode != 0
    assert "release/" + NEW_RC in result.stderr + result.stdout


def test_release_pr_requires_repo(sandbox: Sandbox) -> None:
    result = sandbox.run("release_pr.py", "--dry-run", "--version", NEW_RC)
    assert result.returncode != 0


# --- tag_and_push.py, update_zenodo_badge.py, verify_release_version.py --------


def test_tag_and_push_refuses_and_names_the_workflow(sandbox: Sandbox) -> None:
    result = sandbox.run("tag_and_push.py")
    assert result.returncode != 0
    assert "release_on_merge.yml" in result.stdout + result.stderr
    assert sandbox.calls("git") == []


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_release_test_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zenodo_badge_never_runs_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load("update_zenodo_badge")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<svg>10.5281/zenodo.999</svg>"

    def no_subprocess(*args, **kwargs):
        raise AssertionError(f"subprocess called: {args}")

    monkeypatch.setattr(module, "OUTPUT_PATH", tmp_path / "zenodo_badge.svg")
    monkeypatch.setattr(module, "fetch_latest_doi", lambda concept: "10.5281/zenodo.999")
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda url: FakeResponse())
    monkeypatch.setattr(module.subprocess, "run", no_subprocess)
    monkeypatch.setattr(sys, "argv", ["update_zenodo_badge.py"])
    assert module.main() == 0
    assert (tmp_path / "zenodo_badge.svg").read_bytes() == b"<svg>10.5281/zenodo.999</svg>"


@pytest.mark.parametrize(
    "tag, ok",
    [(NEW_RC, True), ("v" + NEW_RC, False), (NEW_FINAL, False), ("main", False), ("", False)],
)
def test_verify_release_version(sandbox: Sandbox, tag: str, ok: bool) -> None:
    init = sandbox.root / "src" / "brkraw" / "__init__.py"
    init.write_text(re.sub(r"__version__\s*=.*", f"__version__ = '{NEW_RC}'", init.read_text(encoding="utf-8")), encoding="utf-8")
    result = sandbox.run("verify_release_version.py", "--tag", tag)
    assert (result.returncode == 0) is ok, result.stdout + result.stderr


# --- workflows, VS Code tasks, contributing guide ----------------------------


def _workflow(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 reads the key `on` as True
    return data


def _step_index(steps: list, needle: str) -> int:
    for i, step in enumerate(steps):
        if needle in (step.get("name", "") + "\n" + str(step.get("run", "")) + "\n" + str(step.get("uses", ""))):
            return i
    raise AssertionError(f"no step with {needle!r}")


def test_release_starts_only_from_the_workflow_not_from_a_tag_push() -> None:
    triggers = _workflow("release.yml")["on"]
    assert "push" not in triggers
    assert "workflow_dispatch" in triggers


def test_tag_and_version_checked_before_release_publish_and_tagging() -> None:
    steps = _workflow("release.yml")["jobs"]["release"]["steps"]
    assert _step_index(steps, "verify_release_version.py") < _step_index(steps, "action-gh-release")
    steps = _workflow("publish.yml")["jobs"]["build"]["steps"]
    assert _step_index(steps, "verify_release_version.py") < _step_index(steps, "python -m build")
    steps = _workflow("release_on_merge.yml")["jobs"]["tag_release"]["steps"]
    assert _step_index(steps, "verify_release_version.py") < _step_index(steps, "git push origin")


def test_final_release_starts_docs_deployment() -> None:
    steps = _workflow("release.yml")["jobs"]["release"]["steps"]
    step = steps[_step_index(steps, "gh workflow run docs.yml")]
    assert "prerelease.outputs.value == 'false'" in step["if"]
    assert _step_index(steps, "action-gh-release") < _step_index(steps, "gh workflow run docs.yml")


def test_ci_runs_when_scripts_change() -> None:
    triggers = _workflow("ci.yml")["on"]
    for event in ("push", "pull_request"):
        assert "scripts/**" in triggers[event]["paths"]


def _tasks() -> list:
    return json.loads((REPO_ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))["tasks"]


def test_vscode_tasks_match_the_workflow() -> None:
    tasks = _tasks()
    labels = [t["label"] for t in tasks]
    for label in ("Test: tests", "Validate: real data (manual)", "Release: prep (local, no network)"):
        assert label in labels
    for task in tasks:
        command = task["command"]
        for banned in ("tag_and_push", "update_zenodo_badge", "release_notes.py", ".venv/"):
            assert banned not in command, (task["label"], banned)
        for script in re.findall(r"scripts/[\w/]+\.py", command):
            assert (REPO_ROOT / script).is_file(), script
        if "release_pr.py" in command:
            assert "--repo BrkRaw/brkraw" in command


def test_contributing_guide_names_every_task() -> None:
    guide = (REPO_ROOT / "docs" / "dev" / "contributing.md").read_text(encoding="utf-8")
    for task in _tasks():
        assert f"`{task['label']}`" in guide, task["label"]
