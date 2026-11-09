"""Tests for zyuka.rights.* and zyuka.compliance.*."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd

from zyuka.commands.init import _LOGFRAME_YML_TEMPLATE, _ZYUKA_YML_TEMPLATE
from zyuka.compliance.consent import check_consent
from zyuka.compliance.dpia import render_dpia
from zyuka.privacy.pseudonymise import pseudonymise_value
from zyuka.rights.retention import list_expired, purge_expired
from zyuka.rights.subject import erase_subject, find_subject
from zyuka.security.keys import generate_key, load_key


def _project(tmp_path: Path, retention_days: int = 1825) -> tuple[Path, Path]:
    """Create a minimal project and return (project_dir, key_path)."""

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    key_path = tmp_path / ".zyuka-keys" / "proj.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    generate_key(key_path)

    (project_dir / "zyuka.yml").write_text(
        _ZYUKA_YML_TEMPLATE.format(
            organisation="Demo NGO",
            programme="Demo",
            data_controller="dpo@example.org",
            retention_days=retention_days,
            key_path=key_path.as_posix(),
            small_cell=5,
        ).replace("retention_days: 1825", f"retention_days: {retention_days}"),
        encoding="utf-8",
    )
    (project_dir / "logframe.yml").write_text(_LOGFRAME_YML_TEMPLATE, encoding="utf-8")
    return project_dir, key_path


def _protected_csv(data_dir: Path, name: str, nrcs: list[str], key_bytes: bytes) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "nrc": [pseudonymise_value(n, key_bytes) for n in nrcs],
            "sex": ["female"] * len(nrcs),
            "round": [name] * len(nrcs),
        }
    )
    path = data_dir / f"protected_{name}.csv"
    df.to_csv(path, index=False)
    return path


def test_find_subject_matches_pseudonymised_rows(tmp_path: Path) -> None:
    project_dir, key_path = _project(tmp_path)
    key = load_key(key_path)
    data_dir = tmp_path / "protected"
    _protected_csv(data_dir, "baseline", ["100001/10/1", "100002/10/2"], key.material)
    _protected_csv(data_dir, "midline", ["100001/10/1"], key.material)

    matches = find_subject(project_dir, data_dir, "100001/10/1")
    assert len(matches) == 2
    assert {m.row_count for m in matches} == {1}


def test_find_subject_returns_empty_when_absent(tmp_path: Path) -> None:
    project_dir, key_path = _project(tmp_path)
    key = load_key(key_path)
    data_dir = tmp_path / "protected"
    _protected_csv(data_dir, "baseline", ["100001/10/1"], key.material)

    matches = find_subject(project_dir, data_dir, "999999/99/9")
    assert matches == []


def test_erase_subject_removes_rows_and_audits(tmp_path: Path) -> None:
    project_dir, key_path = _project(tmp_path)
    key = load_key(key_path)
    data_dir = tmp_path / "protected"
    _protected_csv(data_dir, "baseline", ["A/1/1", "B/2/2", "C/3/3"], key.material)

    report = erase_subject(project_dir, data_dir, "B/2/2")
    assert report.rows_removed == 1

    remaining = pd.read_csv(data_dir / "protected_baseline.csv")
    assert len(remaining) == 2
    # Raw identifier never appears in the audit log
    audit = (project_dir / ".zyuka" / "audit.jsonl").read_text(encoding="utf-8")
    assert "B/2/2" not in audit
    assert "subject.erase" in audit


def test_retention_lists_and_purges_old_files(tmp_path: Path) -> None:
    project_dir, _ = _project(tmp_path, retention_days=1)
    outputs = project_dir / "outputs"
    outputs.mkdir()
    old = outputs / "old.csv"
    old.write_text("x\n1", encoding="utf-8")
    # Backdate mtime to 10 days ago
    long_ago = time.time() - (10 * 86400)
    os.utime(old, (long_ago, long_ago))

    expired = list_expired(project_dir, outputs)
    assert len(expired) == 1
    assert expired[0].age_days >= 9

    removed = purge_expired(project_dir, [expired[0].path])
    assert removed == [old]
    assert not old.exists()


def test_retention_refuses_to_delete_outside_project(tmp_path: Path) -> None:
    project_dir, _ = _project(tmp_path)
    outsider = tmp_path / "not-in-project.csv"
    outsider.write_text("a", encoding="utf-8")

    from zyuka.errors import ZyukaError

    try:
        purge_expired(project_dir, [outsider])
    except ZyukaError as exc:
        assert "outside" in str(exc.message)
    else:
        raise AssertionError("purge_expired did not refuse an outsider path")


def test_dpia_writes_markdown_and_html(tmp_path: Path) -> None:
    project_dir, _ = _project(tmp_path)
    scan_json = tmp_path / "scan.json"
    scan_json.write_text(
        json.dumps(
            {
                "columns": [
                    {
                        "name": "nrc",
                        "risk": "high",
                        "signals": ["value:nrc"],
                        "suggested_action": "pseudonymise",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "dpia_out"
    render_dpia(project_dir, scan_json=scan_json, out_dir=out)
    assert (out / "dpia.md").exists()
    assert (out / "dpia.html").exists()
    md = (out / "dpia.md").read_text(encoding="utf-8")
    assert "Demo NGO" in md
    assert "nrc" in md


def test_consent_report_counts_and_filters(tmp_path: Path) -> None:
    project_dir, _ = _project(tmp_path)
    data = tmp_path / "survey.csv"
    pd.DataFrame(
        {
            "pid_seed": ["P1", "P2", "P3", "P4"],
            "demographics/consent": ["yes", "no", "yes", "yes"],
        }
    ).to_csv(data, index=False)

    report = check_consent(project_dir, data, exclude=True)
    assert report.consented == 3
    assert report.non_consented == 1
    assert report.filtered_path is not None
    filtered = pd.read_csv(report.filtered_path)
    assert len(filtered) == 3


def test_consent_report_reports_missing_column(tmp_path: Path) -> None:
    project_dir, _ = _project(tmp_path)
    data = tmp_path / "survey.csv"
    pd.DataFrame({"pid_seed": ["P1"]}).to_csv(data, index=False)

    report = check_consent(project_dir, data)
    assert report.consented == 0
    assert report.non_consented == 1
