"""Integration tests for the one-shot pipeline, demo and init wizard."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from linga.cli import app
from linga.demo import run_demo
from linga.pipeline import run_pipeline
from linga.synthetic import ROUND_NAMES, write_rounds


def _demo_project(tmp_path: Path) -> Path:
    """Write a minimal project with synthetic data and return its directory."""

    project_dir = tmp_path / "proj"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            str(project_dir),
            "--yes",
            "--organisation",
            "Demo NGO",
            "--programme",
            "Rural Livelihoods",
            "--data-controller",
            "privacy@demo.org",
        ],
    )
    assert result.exit_code == 0, result.output

    # Generate a key so the pipeline can pseudonymise.
    key_path = project_dir.parent / ".linga-keys" / "proj.key"
    key_result = runner.invoke(app, ["key", "generate", str(key_path)])
    assert key_result.exit_code == 0, key_result.output

    write_rounds(project_dir / "data")
    return project_dir


def test_init_writes_templates(tmp_path: Path) -> None:
    project_dir = tmp_path / "new"
    runner = CliRunner()
    result = runner.invoke(app, ["init", str(project_dir), "--yes"])
    assert result.exit_code == 0, result.output
    assert (project_dir / "linga.yml").exists()
    assert (project_dir / "logframe.yml").exists()


def test_init_refuses_to_overwrite(tmp_path: Path) -> None:
    project_dir = tmp_path / "exists"
    project_dir.mkdir()
    (project_dir / "linga.yml").write_text("already here", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["init", str(project_dir), "--yes"])
    assert result.exit_code != 0


def test_run_pipeline_end_to_end(tmp_path: Path) -> None:
    project_dir = _demo_project(tmp_path)
    result = run_pipeline(
        project_dir=project_dir,
        rounds=list(ROUND_NAMES),
        open_report=False,
    )
    assert result.report_html.exists()
    assert result.report_excel.exists()
    assert result.results_json.exists()
    assert len(result.rounds) == 3
    for ro in result.rounds:
        assert ro.protected_path.exists()
        assert ro.manifest_path.exists()
        assert ro.quality_flags_path.exists()
        assert ro.scan_path.exists()
    # Audit log was appended to
    audit_log = project_dir / ".linga" / "audit.jsonl"
    assert audit_log.exists()
    assert audit_log.read_text(encoding="utf-8").count("\n") >= 4


def test_run_pipeline_encrypts_outputs(tmp_path: Path) -> None:
    project_dir = _demo_project(tmp_path)
    result = run_pipeline(
        project_dir=project_dir,
        rounds=list(ROUND_NAMES),
        encrypt=True,
    )
    for ro in result.rounds:
        assert ro.protected_path.with_suffix(".csv.enc").exists()
    assert result.report_excel.with_suffix(".xlsx.enc").exists()


def test_lingaerror_renders_as_plain_message(tmp_path: Path) -> None:
    """Running a command that raises ``LingaError`` must produce a clean message,
    not a traceback, and exit non-zero."""

    runner = CliRunner()
    missing = tmp_path / "nope.csv"
    result = runner.invoke(app, ["scan", str(missing)])
    assert result.exit_code == 1, result.output
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_key_rotate_appends_audit_entry(tmp_path: Path) -> None:
    """``key rotate`` is a mutating action and must be recorded in the audit log."""

    import json

    project_dir = _demo_project(tmp_path)
    result = run_pipeline(project_dir=project_dir, rounds=list(ROUND_NAMES))
    assert result.rounds

    old_key = project_dir.parent / ".linga-keys" / "proj.key"
    new_key = project_dir.parent / ".linga-keys" / "proj-new.key"

    runner = CliRunner()
    rot = runner.invoke(
        app,
        [
            "key",
            "rotate",
            str(old_key),
            str(new_key),
            "--data",
            str(project_dir / "outputs" / "protected"),
            "--project",
            str(project_dir),
        ],
    )
    assert rot.exit_code == 0, rot.output

    audit_log = project_dir / ".linga" / "audit.jsonl"
    entries = [json.loads(line) for line in audit_log.read_text().splitlines()]
    rotate_entries = [e for e in entries if e.get("command") == "key.rotate"]
    assert len(rotate_entries) == 1
    settings = rotate_entries[0]["settings"]
    assert "old_fingerprint" in settings
    assert "new_fingerprint" in settings
    assert settings["old_fingerprint"] != settings["new_fingerprint"]


def test_demo_produces_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "linga-demo"
    report_path = run_demo(out_dir=out_dir, open_report=False)
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    # Report was rendered with the demo org/programme.
    assert "Example NGO" in text
    # Protected data was written for every round.
    for round_name in ROUND_NAMES:
        assert (out_dir / "outputs" / "protected" / f"protected_{round_name}.csv").exists()
    # IPTT workbook exists.
    assert (out_dir / "outputs" / "report" / "iptt.xlsx").exists()
