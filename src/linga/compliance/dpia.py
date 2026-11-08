"""DPIA (Data Protection Impact Assessment) starter generator.

Writes a Markdown + HTML starter pre-filled from:

- the ``linga.yml`` organisation / programme / data-controller fields,
- the most recent PII scan (if a path is given), summarised by risk level.

The result is a *starter* — it tells the user what Linga can observe about
the dataset, and lists the questions they still need to answer themselves
(lawful basis, retention justification, cross-border transfers, etc.).

Nothing in the generated file contains raw values; only column names,
counts and risk labels.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from linga import __version__
from linga.config import load_linga_config
from linga.errors import LingaError

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _context(project_dir: Path, scan_json: Path | None) -> dict[str, Any]:
    cfg_path = Path(project_dir) / "linga.yml"
    if not cfg_path.exists():
        raise LingaError(
            "No linga.yml found in the project directory.",
            suggest="Run `linga init` first.",
        )
    cfg = load_linga_config(cfg_path)

    scan_summary: dict[str, Any] = {"columns": [], "counts": {"high": 0, "medium": 0, "low": 0}}
    if scan_json is not None and Path(scan_json).exists():
        data = json.loads(Path(scan_json).read_text(encoding="utf-8"))
        for col in data.get("columns", []):
            risk = col.get("risk", "low")
            scan_summary["columns"].append(
                {
                    "name": col.get("name"),
                    "risk": risk,
                    "signals": col.get("signals", []),
                    "action": col.get("suggested_action", ""),
                }
            )
            scan_summary["counts"][risk] = scan_summary["counts"].get(risk, 0) + 1

    return {
        "organisation": cfg.organisation,
        "programme": cfg.programme,
        "data_controller": cfg.data_controller_contact,
        "retention_days": cfg.retention_days,
        "small_cell": cfg.protection.small_cell_threshold,
        "scan": scan_summary,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "version": __version__,
    }


def render_dpia(
    project_dir: Path,
    scan_json: Path | None = None,
    out_dir: Path = Path("outputs/dpia"),
) -> list[Path]:
    """Render DPIA starter to Markdown + HTML. Returns the paths written."""

    context = _context(project_dir, scan_json)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    md = env.get_template("dpia.md.j2").render(**context)
    html = env.get_template("dpia.html.j2").render(**context)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "dpia.md"
    html_path = out_dir / "dpia.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return [md_path, html_path]
