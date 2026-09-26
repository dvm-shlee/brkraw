"""Tests for the shared test base: environment isolation, approved fixtures, synthetic data."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

import brkraw
from brkraw.apps.loader import info as info_resolver
from brkraw.core import config as config_core

from tests.agent_fixtures import find_approved_zips, parse_fixture_readme
from tests.conftest import REAL_HOME
from tests.helpers import SYNTH_MARKERS, isolate_brkraw_env, make_synthetic_study, zip_synthetic_study


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------


def test_config_home_is_a_temporary_folder():
    root = config_core.resolve_root()
    assert os.environ.get("BRKRAW_CONFIG_HOME") == str(root)
    assert REAL_HOME not in root.parents
    assert root != REAL_HOME / ".brkraw"


def test_home_is_a_temporary_folder():
    assert Path.home() != REAL_HOME
    assert Path.home().is_dir()


def test_no_session_variables_leak_into_tests():
    leaked = [k for k in os.environ if k.startswith("BRKRAW_") and k not in ("BRKRAW_CONFIG_HOME", "BRKRAW_AGENT_FIXTURES")]
    assert leaked == []


def test_isolate_removes_session_variables_and_keeps_fixture_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BRKRAW_PATH", "/somewhere/study")
    monkeypatch.setenv("BRKRAW_SCAN_ID", "3")
    monkeypatch.setenv("BRKRAW_CONVERT_OUTPUT", "/out")
    monkeypatch.setenv("BRKRAW_AGENT_FIXTURES", "/fixtures")
    isolate_brkraw_env(monkeypatch, tmp_path)
    assert "BRKRAW_PATH" not in os.environ
    assert "BRKRAW_SCAN_ID" not in os.environ
    assert "BRKRAW_CONVERT_OUTPUT" not in os.environ
    assert os.environ["BRKRAW_AGENT_FIXTURES"] == "/fixtures"
    assert os.environ["BRKRAW_CONFIG_HOME"] == str(tmp_path / "config")
    assert os.environ["HOME"] == str(tmp_path / "home")
    assert (tmp_path / "home").is_dir()


# ---------------------------------------------------------------------------
# Approved agent fixtures
# ---------------------------------------------------------------------------

_HEADER = (
    "| File | ParaVision | Made by / date | Prune spec (file + SHA-256) | Approved |\n"
    "| --- | --- | --- | --- | --- |\n"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(rel: str, sha: str, state: str) -> str:
    return f"| `{rel}` (zip sha256 `{sha}`) | x | Park | `spec.yaml` sha256 `{'b' * 64}` | {state} |\n"


def test_parse_fixture_readme_reads_path_zip_hash_and_exact_approval():
    h = "A" * 64
    text = "# t\n" + _HEADER + _row("pv5.1/a.zip", h, "승인") + _row("pv5.1/b.zip", h, "승인 대기")
    rows = parse_fixture_readme(text)
    assert rows == [
        {"path": "pv5.1/a.zip", "sha256": "a" * 64, "approved": True},
        {"path": "pv5.1/b.zip", "sha256": "a" * 64, "approved": False},
    ]


def test_find_approved_zips_uses_only_approved_rows_with_matching_hash(tmp_path):
    folder = tmp_path / "agent-fixtures"
    (folder / "pv5.1").mkdir(parents=True)
    (folder / "pv6").mkdir()
    ok = folder / "pv5.1" / "ok.zip"
    bad = folder / "pv5.1" / "bad.zip"
    wait = folder / "pv5.1" / "wait.zip"
    other = folder / "pv6" / "other.zip"
    for p in (ok, bad, wait, other):
        p.write_bytes(p.name.encode())
    text = _HEADER
    text += _row("pv5.1/ok.zip", _sha(ok), "승인")
    text += _row("pv5.1/bad.zip", "0" * 64, "승인")
    text += _row("pv5.1/wait.zip", _sha(wait), "승인 대기")
    text += _row("pv5.1/missing.zip", "1" * 64, "승인")
    text += _row("pv6/other.zip", _sha(other), "승인")
    (folder / "README.md").write_text(text, encoding="utf-8")

    found, reasons = find_approved_zips(folder, "pv5.1")

    assert found == [ok]
    joined = "\n".join(reasons)
    assert "bad.zip" in joined and "SHA-256" in joined
    assert "wait.zip" in joined and "not approved" in joined
    assert "missing.zip" in joined and "missing" in joined
    assert "other.zip" not in joined


def test_find_approved_zips_without_folder_or_readme(tmp_path):
    found, reasons = find_approved_zips(tmp_path / "nowhere", "pv5.1")
    assert found == [] and "not found" in reasons[0]
    (tmp_path / "empty").mkdir()
    found, reasons = find_approved_zips(tmp_path / "empty", "pv5.1")
    assert found == [] and "README" in reasons[0]


@pytest.mark.agent_fixtures
def test_approved_zips_fixture_copies_or_skips(approved_zips, tmp_path):
    # Runs against the real local folder when present; skips on CI.
    paths = approved_zips("pv5.1")
    for p in paths:
        assert tmp_path in p.parents
        assert p.suffix == ".zip"


# ---------------------------------------------------------------------------
# Synthetic PvDataset
# ---------------------------------------------------------------------------


def test_synthetic_study_loads_as_folder_and_zip(tmp_path):
    study = make_synthetic_study(tmp_path / "study", pv="6.0.1", scans={1: "FLASH", 3: "RARE"})
    zipped = zip_synthetic_study(study, tmp_path / "study.zip")
    for src in (study, zipped):
        loader = brkraw.load(str(src))
        assert sorted(loader.avail) == [1, 3]
        info = info_resolver.study(loader) or {}
        assert info["Subject"]["ID"] == SYNTH_MARKERS["subject_id"]
        assert info["Study"]["ID"] == SYNTH_MARKERS["study_name"]


def test_synthetic_study_has_study_scan_and_raw_files(tmp_path):
    study = make_synthetic_study(tmp_path / "s", pv="360.3.3", scans={2: "EPI"})
    names = sorted(p.relative_to(study).as_posix() for p in study.rglob("*") if p.is_file())
    assert names == [
        "2/AdjStatePerScan",
        "2/acqp",
        "2/fid",
        "2/method",
        "2/pdata/1/2dseq",
        "2/pdata/1/procs",
        "2/pdata/1/reco",
        "2/pdata/1/visu_pars",
        "AdjStatePerStudy",
        "ScanProgram.scanProgram",
        "subject",
    ]
