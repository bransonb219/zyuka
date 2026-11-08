"""One-shot pipeline: check → scan → protect → compute → report → audit.

Both ``linga run`` (single round) and ``linga demo`` (all rounds) call into
this module. The orchestration keeps all writes under the project's
``outputs/`` directory so a user can re-run the pipeline idempotently.

The pipeline deliberately never prints raw data values. It writes column
names, counts and SHA-256 hashes to the audit log and relies on each
sub-step to enforce its own suppression / masking rules.
"""

from __future__ import annotations

import json
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from linga.config import LingaConfig, LogframeConfig, load_linga_config, load_logframe
from linga.errors import LingaError
from linga.indicators.pipeline import compute_from_rounds
from linga.ingest.rounds import load_round
from linga.pipeline_support import protect_dataframe
from linga.privacy.scanner import scan_dataframe
from linga.quality.report import run_quality
from linga.reports.excel import render_excel
from linga.reports.html import render_html
from linga.security.audit import write_entry
from linga.security.crypto import encrypt_file
from linga.security.keys import Key, load_key


@dataclass
class RoundOutputs:
    """Paths written for a single round."""

    round_name: str
    raw_path: Path
    protected_path: Path
    manifest_path: Path
    quality_flags_path: Path
    scan_path: Path


@dataclass
class PipelineResult:
    """What ``run_pipeline`` produced."""

    project_dir: Path
    out_dir: Path
    report_html: Path
    report_excel: Path
    results_json: Path
    rounds: list[RoundOutputs] = field(default_factory=list)


def _find_round_file(project_dir: Path, round_name: str) -> Path:
    """Locate the raw export for ``round_name`` under the project directory."""

    data_dir = project_dir / "data"
    patterns = (
        f"survey_{round_name}.csv",
        f"survey_{round_name}.xlsx",
        f"{round_name}.csv",
        f"{round_name}.xlsx",
    )
    for name in patterns:
        candidate = data_dir / name
        if candidate.exists():
            return candidate
    raise LingaError(
        f"Could not find a raw export for round '{round_name}'.",
        suggest=(
            f"Place one of {', '.join(patterns)} under {data_dir}, "
            "or pass --data pointing to the file."
        ),
    )


def _write_scan_json(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = scan_dataframe(df)
    out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def _process_round(
    *,
    round_name: str,
    raw_path: Path,
    out_dir: Path,
    config: LingaConfig | None,
    logframe: LogframeConfig | None,
    key: Key | None,
    audit_log: Path,
) -> tuple[RoundOutputs, pd.DataFrame]:
    """Run check + scan + protect for one round and return paths + protected df."""

    df = load_round(raw_path, round_name)

    quality = run_quality(df)
    quality_flags_path = out_dir / "quality" / f"quality_flags_{round_name}.csv"
    quality_flags_path.parent.mkdir(parents=True, exist_ok=True)
    quality.flags.to_csv(quality_flags_path, index=False)

    scan_path = out_dir / "scan" / f"scan_{round_name}.json"
    _write_scan_json(df, scan_path)

    protected_df, manifest_json = protect_dataframe(df, config=config, logframe=logframe, key=key)
    protected_path = out_dir / "protected" / f"protected_{round_name}.csv"
    protected_path.parent.mkdir(parents=True, exist_ok=True)
    protected_df.to_csv(protected_path, index=False)
    manifest_path = protected_path.with_suffix(".manifest.json")
    manifest_path.write_text(manifest_json, encoding="utf-8")

    write_entry(
        audit_log,
        command="run.round",
        inputs=[raw_path],
        outputs=[protected_path, manifest_path, quality_flags_path, scan_path],
        rows=len(protected_df),
        columns=len(protected_df.columns),
        settings={"round": round_name},
    )

    return (
        RoundOutputs(
            round_name=round_name,
            raw_path=raw_path,
            protected_path=protected_path,
            manifest_path=manifest_path,
            quality_flags_path=quality_flags_path,
            scan_path=scan_path,
        ),
        protected_df,
    )


def _render_outputs(
    *,
    protected_rounds: dict[str, pd.DataFrame],
    logframe: LogframeConfig | None,
    config: LingaConfig | None,
    out_dir: Path,
    audit_log: Path,
) -> tuple[Path, Path, Path]:
    """Compute indicators and render HTML + Excel."""

    results_path = out_dir / "indicator_results.json"
    html_path = out_dir / "report" / "report.html"
    excel_path = out_dir / "report" / "iptt.xlsx"

    if logframe is None:
        results: dict[str, Any] = {
            "rounds": list(protected_rounds),
            "indicators": [],
            "validation": [
                {
                    "code": "no-logframe",
                    "message": "No logframe.yml found; skipping indicators.",
                    "suggestion": "Run `linga init` or add logframe.yml.",
                }
            ],
        }
    else:
        computed = compute_from_rounds(
            logframe=logframe,
            rounds=protected_rounds,
            config=config,
        )
        results = computed.to_dict()

    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    organisation = config.organisation if config else "Your Organisation"
    programme = config.programme if config else "Programme"
    data_controller = config.data_controller_contact if config else "Data Controller"
    small_cell = config.protection.small_cell_threshold if config else 5

    render_html(
        results,
        html_path,
        organisation=organisation,
        programme=programme,
        data_controller=data_controller,
        small_cell_threshold=small_cell,
    )
    render_excel(
        results,
        excel_path,
        metadata={
            "organisation": organisation,
            "programme": programme,
            "data_controller": data_controller,
        },
    )

    write_entry(
        audit_log,
        command="run.report",
        inputs=[],
        outputs=[results_path, html_path, excel_path],
        rows=len(results.get("indicators", [])),
        columns=len(results.get("rounds", [])),
        settings={"organisation": organisation, "programme": programme},
    )
    return html_path, excel_path, results_path


def _maybe_encrypt(paths: list[Path], key: Key | None, audit_log: Path) -> None:
    if key is None:
        return
    for p in paths:
        if not p.exists():
            continue
        enc = encrypt_file(p, p.with_suffix(p.suffix + ".enc"), key)
        write_entry(
            audit_log,
            command="run.encrypt",
            inputs=[p],
            outputs=[enc],
            settings={"key_fingerprint": key.fingerprint},
        )


def _load_project(
    project_dir: Path,
) -> tuple[LingaConfig | None, LogframeConfig | None, Key | None]:
    cfg_path = project_dir / "linga.yml"
    lf_path = project_dir / "logframe.yml"
    config = load_linga_config(cfg_path) if cfg_path.exists() else None
    logframe = load_logframe(lf_path) if lf_path.exists() else None
    key: Key | None = None
    if config is not None and Path(config.key_path).exists():
        key = load_key(config.key_path)
    return config, logframe, key


def run_pipeline(
    project_dir: Path,
    round_name: str | None = None,
    encrypt: bool = False,
    open_report: bool = False,
    rounds: list[str] | None = None,
) -> PipelineResult:
    """Run the full pipeline for one or many rounds.

    ``round_name`` is kept for compatibility with ``linga run --round``; when
    ``rounds`` is supplied (as the demo does) all are processed in one go.
    """

    project_dir = Path(project_dir).resolve()
    out_dir = project_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    config, logframe, key = _load_project(project_dir)
    audit_log = project_dir / ".linga" / "audit.jsonl"
    audit_log.parent.mkdir(parents=True, exist_ok=True)

    to_process: list[str] = list(rounds) if rounds else [round_name or "baseline"]

    round_outputs: list[RoundOutputs] = []
    protected_rounds: dict[str, pd.DataFrame] = {}
    for name in to_process:
        raw_path = _find_round_file(project_dir, name)
        out, protected_df = _process_round(
            round_name=name,
            raw_path=raw_path,
            out_dir=out_dir,
            config=config,
            logframe=logframe,
            key=key,
            audit_log=audit_log,
        )
        round_outputs.append(out)
        protected_rounds[name] = protected_df

    html_path, excel_path, results_path = _render_outputs(
        protected_rounds=protected_rounds,
        logframe=logframe,
        config=config,
        out_dir=out_dir,
        audit_log=audit_log,
    )

    if encrypt:
        _maybe_encrypt(
            [o.protected_path for o in round_outputs] + [excel_path, results_path],
            key,
            audit_log,
        )

    if open_report:
        webbrowser.open(html_path.as_uri())

    return PipelineResult(
        project_dir=project_dir,
        out_dir=out_dir,
        report_html=html_path,
        report_excel=excel_path,
        results_json=results_path,
        rounds=round_outputs,
    )
