"""Thin orchestration: load inputs → render HTML + Excel → optionally open.

Importers: :mod:`linga.commands.report` and :mod:`linga.pipeline`.
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Any

import pandas as pd

from linga.config import load_linga_config
from linga.reports.excel import render_excel
from linga.reports.html import render_html


def _load_results(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return data


def _load_quality_flags(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def render_report(
    project_dir: Path,
    results_json: Path,
    out_dir: Path,
    open_report: bool = False,
    quality_flags_path: Path | None = None,
) -> Path:
    """Render HTML + Excel from the indicator results JSON on disk."""

    project_dir = Path(project_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = project_dir / "linga.yml"
    if cfg_path.exists():
        cfg = load_linga_config(cfg_path)
        organisation = cfg.organisation
        programme = cfg.programme
        data_controller = cfg.data_controller_contact
        small_cell = cfg.protection.small_cell_threshold
    else:
        organisation = "Your Organisation"
        programme = "Programme"
        data_controller = "Data Controller"
        small_cell = 5

    results = _load_results(results_json)
    quality_flags = (
        _load_quality_flags(quality_flags_path) if quality_flags_path is not None else None
    )

    html_path = render_html(
        results,
        out_dir / "report.html",
        organisation=organisation,
        programme=programme,
        data_controller=data_controller,
        quality={"flagged rows": len(quality_flags) if quality_flags is not None else 0},
        small_cell_threshold=small_cell,
    )
    render_excel(
        results,
        out_dir / "iptt.xlsx",
        quality_flags=quality_flags,
        metadata={
            "organisation": organisation,
            "programme": programme,
            "data_controller": data_controller,
        },
    )

    if open_report:
        webbrowser.open(html_path.as_uri())
    return html_path
