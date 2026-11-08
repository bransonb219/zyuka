"""Excel workbook writer — IPTT + disaggregation + quality + metadata.

The IPTT (Indicator Performance Tracking Table) sheet follows the standard
donor layout: one row per indicator with baseline, per-round actuals, target
and status. Disaggregated values are written to per-column sheets. The
quality-flags sheet uses the DataFrame from
:class:`linga.quality.report.QualityReport`.

All string cells are routed through :func:`sanitise_cell` so no respondent-
authored formula survives into the workbook.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from linga import __version__
from linga.security.sanitize import sanitise_cell

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="334466")


def _write_header(ws: Worksheet, headers: list[str]) -> None:
    for col_idx, title in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=title)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL


def _write_row(ws: Worksheet, row_idx: int, values: list[Any]) -> None:
    for col_idx, value in enumerate(values, start=1):
        ws.cell(row=row_idx, column=col_idx, value=sanitise_cell(value))


def _iptt_sheet(wb: Workbook, results: dict[str, Any]) -> None:
    ws = wb.create_sheet("IPTT")
    rounds = results.get("rounds", [])
    headers = ["Code", "Indicator", "Type", "Unit", "Baseline"]
    for r in rounds:
        headers.extend([f"{r}", f"{r} target", f"{r} % target", f"{r} status"])
    _write_header(ws, headers)

    for i, ind in enumerate(results.get("indicators", []), start=2):
        row: list[Any] = [
            ind.get("code"),
            ind.get("name"),
            ind.get("type"),
            ind.get("unit"),
            next(
                (
                    p.get("value")
                    for p in ind.get("longitudinal", [])
                    if p.get("round") == "baseline"
                ),
                None,
            ),
        ]
        for round_name in rounds:
            point: dict[str, Any] = next(
                (p for p in ind.get("longitudinal", []) if p.get("round") == round_name), {}
            )
            row.extend(
                [
                    point.get("value"),
                    point.get("target"),
                    point.get("percent_of_target"),
                    point.get("status"),
                ]
            )
        _write_row(ws, i, row)


def _disaggregation_sheets(wb: Workbook, results: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for ind in results.get("indicators", []):
        for round_name, round_data in ind.get("per_round", {}).items():
            for col, mapping in (round_data.get("by") or {}).items():
                for value, iv in mapping.items():
                    rows.append(
                        {
                            "code": ind.get("code"),
                            "indicator": ind.get("name"),
                            "round": round_name,
                            "disaggregation": col,
                            "value": value,
                            "n": iv.get("value") if isinstance(iv, dict) else None,
                            "numerator": iv.get("numerator") if isinstance(iv, dict) else None,
                            "denominator": iv.get("denominator") if isinstance(iv, dict) else None,
                        }
                    )
    if not rows:
        return
    ws = wb.create_sheet("Disaggregation")
    df = pd.DataFrame(rows)
    _write_header(ws, list(df.columns))
    for i, record in enumerate(df.to_dict(orient="records"), start=2):
        _write_row(ws, i, list(record.values()))


def _quality_sheet(wb: Workbook, quality_flags: pd.DataFrame | None) -> None:
    if quality_flags is None or quality_flags.empty:
        return
    ws = wb.create_sheet("Quality flags")
    _write_header(ws, list(quality_flags.columns))
    for i, record in enumerate(quality_flags.to_dict(orient="records"), start=2):
        _write_row(ws, i, list(record.values()))


def _metadata_sheet(wb: Workbook, metadata: dict[str, Any]) -> None:
    ws = wb.create_sheet("Metadata")
    _write_header(ws, ["Field", "Value"])
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    base: list[tuple[str, Any]] = [
        ("Generated", now),
        ("Linga version", __version__),
    ]
    extras = list(metadata.items())
    for i, (k, v) in enumerate(base + extras, start=2):
        _write_row(ws, i, [k, v])


def render_excel(
    results: dict[str, Any],
    out_path: Path,
    quality_flags: pd.DataFrame | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write an IPTT + disaggregation + quality + metadata workbook."""

    wb = Workbook()
    # Workbook() always creates a default sheet; remove it and let our
    # named sheets be first.
    default = wb.active
    if default is not None:
        wb.remove(default)

    _iptt_sheet(wb, results)
    _disaggregation_sheets(wb, results)
    _quality_sheet(wb, quality_flags)
    _metadata_sheet(wb, metadata or {})

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
