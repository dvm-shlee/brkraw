"""Shared test helpers: module loading, environment isolation, synthetic PvDatasets."""
from __future__ import annotations

import importlib
import os
import struct
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Kept while tests run: the config home set by the isolation itself and the
# optional override for the agent-fixtures folder.
KEEP_ENV = ("BRKRAW_CONFIG_HOME", "BRKRAW_AGENT_FIXTURES")


def prep_module(core_level: str, parser: str):
    module_path = f"brkraw.{core_level}"
    mod = importlib.import_module(module_path)
    return getattr(mod, parser)


def isolate_brkraw_env(monkeypatch, base: Path) -> None:
    """Point brkraw's config home and HOME into ``base`` and drop session variables.

    ``brkraw session`` exports ``BRKRAW_PATH``, ``BRKRAW_SCAN_ID``,
    ``BRKRAW_CONVERT_*`` and similar variables that change command defaults;
    without ``BRKRAW_CONFIG_HOME`` brkraw reads ``~/.brkraw``; ``brkraw init``
    looks at ``Path.home()``. Tests must see none of the developer's own
    settings.
    """
    base = Path(base)
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    for key in list(os.environ):
        if key.startswith("BRKRAW_") and key not in KEEP_ENV:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRKRAW_CONFIG_HOME", str(base / "config"))
    monkeypatch.setenv("HOME", str(home))


# ---------------------------------------------------------------------------
# Synthetic ParaVision-like datasets
# ---------------------------------------------------------------------------

# Every identifying value is a unique marker (ZQX… or a fixed digit string) so
# prune tests can search outputs for it. No real data is involved.
SYNTH_MARKERS: Dict[str, str] = {
    "name": "ZQXDoeJohn",
    "subject_id": "ZQXmouse77",
    "study_name": "ZQXstudyAlpha",
    "operator": "ZQXoperatorKim",
    "owner": "ZQXloginuser",
    "institution": "ZQXUniversityOfNowhere",
    "station": "ZQXStation94",
    "referral": "ZQXDrReferrer",
    "comment": "ZQXfreeTextComment",
    "birth": "19870412",
    "order": "ZQXorder5566",
    "folder": "20240315_101010_ZQXDoeJohn_1_1",
    "abs_date": "1710497410",
    "uid": "2.16.840.1.113654.2.ZQX",
}


def _jcamp(title: str, owner: str, path_comment: str, params: List[Tuple[str, str]]) -> str:
    lines = [
        f"##TITLE=Parameter List, {title}",
        "##JCAMPDX=4.24",
        "##DATATYPE=Parameter Values",
        "##ORIGIN=Bruker BioSpin MRI GmbH",
        f"##OWNER={owner}",
        f"$$ Fri Mar 15 10:10:10 2024 EDT (UT-4h)  {owner}",
        f"$$ {path_comment}",
    ]
    for key, value in params:
        lines.append(f"##${key}={value}")
    lines.append("##END=")
    return "\n".join(lines) + "\n"


def _s(text: str) -> str:
    """JCAMP string value: size line, then <text>."""
    return f"( {max(len(text) + 1, 16)} )\n<{text}>"


def make_synthetic_study(
    root: Path,
    *,
    pv: str = "6.0.1",
    scans: Optional[Dict[int, str]] = None,
) -> Path:
    """Write a small ParaVision-like study folder at ``root`` and return it.

    ``scans`` maps scan id -> method name (default ``{1: "FLASH", 3: "RARE"}``).
    Each scan has acqp, method, fid, AdjStatePerScan and pdata/1 with
    visu_pars, reco, procs and a 4x4 int16 2dseq. Study files: subject,
    AdjStatePerStudy, ScanProgram.scanProgram. Values carry SYNTH_MARKERS,
    JCAMP files carry ``##OWNER`` and ``$$`` comment lines with a source path.
    The images have no real geometry: use them for loading, info and file
    handling, not for checking conversion output.
    """
    scans = scans or {1: "FLASH", 3: "RARE"}
    m = SYNTH_MARKERS
    iso = not pv.startswith("5")
    date_txt = "2024-03-15T10:10:10,123-0400" if iso else "10:10:10 15 Mar 2024"
    title = f"ParaVision {pv}"
    base = f"/opt/PV{pv}/data/{m['owner']}/nmr/{m['folder']}"
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    subject = [
        ("SUBJECT_name_string", _s(m["name"])),
        ("SUBJECT_id", _s(m["subject_id"])),
        ("SUBJECT_study_name", _s(m["study_name"])),
        ("SUBJECT_study_nr", "3"),
        ("SUBJECT_dbirth", _s(m["birth"])),
        ("SUBJECT_date", _s(date_txt)),
        ("SUBJECT_abs_date", "(" + m["abs_date"] + ", 123, -240)"),
        ("SUBJECT_referral", _s(m["referral"])),
        ("SUBJECT_comment", _s(m["comment"])),
        ("SUBJECT_study_instance_uid", _s(m["uid"] + ".1")),
        ("SUBJECT_institution", _s(m["institution"])),
        ("SUBJECT_type", "Quadruped"),
        ("SUBJECT_entry", "SUBJ_ENTRY_HeadFirst"),
        ("SUBJECT_position", "SUBJ_POS_Supine"),
        ("SUBJECT_sex_animal", "MALE"),
        ("SUBJECT_weight", "0.025"),
    ]
    (root / "subject").write_text(_jcamp(title, m["owner"], base + "/subject", subject), encoding="utf-8")
    (root / "AdjStatePerStudy").write_text(
        _jcamp(title, m["owner"], base + "/AdjStatePerStudy", [("ADJ_note", _s(m["operator"]))]),
        encoding="utf-8",
    )
    (root / "ScanProgram.scanProgram").write_text(
        f"<scanProgram><owner>{m['owner']}</owner><name>{m['name']}</name></scanProgram>\n",
        encoding="utf-8",
    )
    for sid, method in scans.items():
        sdir = root / str(sid)
        pdir = sdir / "pdata" / "1"
        pdir.mkdir(parents=True, exist_ok=True)
        acqp = [
            ("ACQ_method", _s(f"Bruker:{method}")),
            ("ACQ_protocol_name", _s(f"{method}_proto")),
            ("ACQ_scan_name", _s(f"{method}_E{sid}")),
            ("ACQ_time", _s(date_txt)),
            ("ACQ_abs_time", "(" + m["abs_date"] + ", 456, -240)"),
            ("ACQ_operator", _s(m["operator"])),
            ("ACQ_institution", _s(m["institution"])),
            ("ACQ_station", _s(m["station"])),
            ("ACQ_sw_version", _s(f"PV-{pv}" if pv.startswith("360") else f"PV {pv}")),
            ("ACQ_calib_date", _s(date_txt)),
            ("NI", "1"),
            ("NR", "1"),
        ]
        method_p = [
            ("Method", f"<Bruker:{method}>" if iso else method),
            ("PVM_EchoTime", "10"),
            ("PVM_RepetitionTime", "2000"),
            ("PVM_Matrix", "( 2 )\n4 4"),
        ]
        visu = [
            ("VisuCoreDim", "2"),
            ("VisuCoreSize", "( 2 )\n4 4"),
            ("VisuCoreFrameCount", "1"),
            ("VisuCoreWordType", "_16BIT_SGN_INT"),
            ("VisuCoreByteOrder", "littleEndian"),
            ("VisuCoreExtent", "( 2 )\n20 20"),
            ("VisuSubjectName", _s(m["name"])),
            ("VisuSubjectId", _s(m["subject_id"])),
            ("VisuSubjectBirthDate", _s(m["birth"])),
            ("VisuSubjectComment", _s(m["comment"])),
            ("VisuStudyId", _s(m["study_name"])),
            ("VisuStudyDate", _s(date_txt)),
            ("VisuStudyUid", _s(m["uid"] + ".2")),
            ("VisuStudyReferringPhysician", _s(m["referral"])),
            ("VisuSeriesDate", _s(date_txt)),
            ("VisuAcqDate", _s(date_txt)),
            ("VisuCreationDate", _s(date_txt)),
            ("VisuUid", _s(m["uid"] + ".3")),
            ("VisuSeriesUid", _s(m["uid"] + ".4")),
            ("VisuInstitution", _s(m["institution"])),
            ("VisuStation", _s(m["station"])),
            ("VisuSystemOrderNumber", _s(m["order"])),
            ("VisuAcqProtocol", _s(f"{method}_proto")),
            ("VisuExperimentNumber", str(sid)),
        ]
        reco = [
            ("RECO_size", "( 2 )\n4 4"),
            ("RECO_time", _s(date_txt)),
            ("RECO_abs_time", "(" + m["abs_date"] + ", 789, -240)"),
            ("RECO_base_image_uid", _s(m["uid"] + ".5")),
        ]
        (sdir / "acqp").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/acqp", acqp), encoding="utf-8")
        (sdir / "method").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/method", method_p), encoding="utf-8")
        (sdir / "fid").write_bytes(b"\x00" * 64)
        (sdir / "AdjStatePerScan").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/AdjStatePerScan", [("ADJ_x", _s(m["name"]))]),
            encoding="utf-8",
        )
        (pdir / "visu_pars").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/visu_pars", visu), encoding="utf-8"
        )
        (pdir / "reco").write_text(_jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/reco", reco), encoding="utf-8")
        (pdir / "procs").write_text(
            _jcamp(title, m["owner"], f"{base}/{sid}/pdata/1/procs", [("PROC_x", _s(m["owner"]))]),
            encoding="utf-8",
        )
        (pdir / "2dseq").write_bytes(struct.pack("<16h", *range(16)))
    return root


def zip_synthetic_study(study: Path, zip_path: Path, *, inner: Optional[str] = None) -> Path:
    """Zip ``study`` with its files under one top folder (default: the marker folder name)."""
    inner = inner or SYNTH_MARKERS["folder"]
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in sorted(Path(study).rglob("*")):
            if p.is_file():
                zf.write(p, f"{inner}/{p.relative_to(study).as_posix()}")
    return Path(zip_path)
