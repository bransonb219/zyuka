"""HTML report writer.

Produces a single self-contained ``report.html`` from the indicator-results
JSON produced by :mod:`linga.indicators.pipeline`. The template is loaded
from the packaged ``templates/`` directory and rendered with Jinja2 in
auto-escape mode so any string from the data is HTML-safe. Charts are
inline SVG data URIs so the file opens offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from linga import __version__
from linga.reports.charts import disaggregation_chart, trend_chart
from linga.reports.summary import build_summary

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _render(context: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    tmpl = env.get_template("report.html.j2")
    return tmpl.render(**context)


def _enrich_indicators(indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach base64 chart URIs in place and return the same list for Jinja."""

    for ind in indicators:
        long_rounds = [p.get("round") for p in ind.get("longitudinal", [])]
        values = [p.get("value") for p in ind.get("longitudinal", [])]
        targets = [p.get("target") for p in ind.get("longitudinal", [])]
        ind["trend_chart"] = trend_chart(
            ind.get("name", ind.get("code", "")), long_rounds, values, targets
        )

        disagg_charts: dict[str, str] = {}
        first_round: dict[str, Any] = next(iter(ind.get("per_round", {}).values()), {})
        for col, mapping in (first_round.get("by") or {}).items():
            disagg_charts[col] = disaggregation_chart(
                ind.get("name", ind.get("code", "")), col, mapping
            )
        ind["disaggregation_charts"] = disagg_charts
    return indicators


def render_html(
    results: dict[str, Any],
    out_path: Path,
    organisation: str = "Your Organisation",
    programme: str = "Programme",
    data_controller: str = "Data Controller",
    quality: dict[str, Any] | None = None,
    small_cell_threshold: int = 5,
) -> Path:
    """Render an HTML report to ``out_path`` and return the path written."""

    context: dict[str, Any] = {
        "organisation": organisation,
        "programme": programme,
        "data_controller": data_controller,
        "version": __version__,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "summary": build_summary(results),
        "validation": results.get("validation", []),
        "indicators": _enrich_indicators(list(results.get("indicators", []))),
        "quality": quality,
        "small_cell_threshold": small_cell_threshold,
    }
    html = _render(context)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
