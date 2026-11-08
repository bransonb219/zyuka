"""Tests for linga.reports.*."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from linga.reports.charts import disaggregation_chart, trend_chart
from linga.reports.excel import render_excel
from linga.reports.html import render_html
from linga.reports.pipeline import render_report
from linga.reports.summary import build_summary

SAMPLE_RESULTS = {
    "rounds": ["baseline", "midline", "endline"],
    "indicators": [
        {
            "code": "OC1.1",
            "name": "Trained participants",
            "type": "count",
            "unit": "people",
            "per_round": {
                "baseline": {
                    "overall": {"value": 10, "numerator": 10, "denominator": None},
                    "by": {
                        "sex": {
                            "female": {"value": 6, "numerator": 6, "denominator": None},
                            "male": {"value": 4, "numerator": 4, "denominator": None},
                        }
                    },
                },
                "midline": {
                    "overall": {"value": 18, "numerator": 18, "denominator": None},
                    "by": {},
                },
                "endline": {
                    "overall": {"value": 40, "numerator": 40, "denominator": None},
                    "by": {},
                },
            },
            "longitudinal": [
                {
                    "round": "baseline",
                    "value": 10,
                    "target": None,
                    "change_from_baseline": 0,
                    "percent_of_target": None,
                    "status": None,
                },
                {
                    "round": "midline",
                    "value": 18,
                    "target": 20,
                    "change_from_baseline": 8,
                    "percent_of_target": 90.0,
                    "status": "on_track",
                },
                {
                    "round": "endline",
                    "value": 40,
                    "target": 50,
                    "change_from_baseline": 30,
                    "percent_of_target": 80.0,
                    "status": "on_track",
                },
            ],
        }
    ],
    "validation": [],
}


def test_summary_describes_status_counts() -> None:
    summary = build_summary(SAMPLE_RESULTS)
    assert summary["indicators"] == 1
    assert summary["rounds"] == 3
    assert summary["counts"].get("on_track") == 2
    assert "on track" in summary["paragraph"]


def test_trend_chart_returns_svg_data_uri() -> None:
    uri = trend_chart("Test", ["a", "b"], [1, 2], [3, 4])
    assert uri.startswith("data:image/svg+xml;base64,")
    assert len(uri) > 100


def test_disaggregation_chart_handles_none_values() -> None:
    mapping = {"female": {"value": 10}, "male": {"value": None}}
    uri = disaggregation_chart("T", "sex", mapping)
    assert uri.startswith("data:image/svg+xml;base64,")


def test_render_html_writes_self_contained_file(tmp_path: Path) -> None:
    out = render_html(
        SAMPLE_RESULTS,
        tmp_path / "report.html",
        organisation="Demo NGO",
        programme="Rural Livelihoods",
        data_controller="privacy@demo.org",
    )
    text = out.read_text(encoding="utf-8")
    assert "Demo NGO" in text
    assert "OC1.1" in text
    assert "data:image/svg+xml;base64" in text
    # No remote asset references.
    assert "http://" not in text
    assert "https://" not in text
    assert "cdn." not in text


def test_render_html_escapes_untrusted_strings(tmp_path: Path) -> None:
    hostile = dict(SAMPLE_RESULTS)
    hostile = {
        **SAMPLE_RESULTS,
        "indicators": [
            {
                **SAMPLE_RESULTS["indicators"][0],
                "name": "<script>alert('xss')</script>",
            }
        ],
    }
    out = render_html(hostile, tmp_path / "r.html", organisation="<img src=x>")
    text = out.read_text(encoding="utf-8")
    assert "<script>alert" not in text
    assert "&lt;script&gt;alert" in text
    assert "<img src=x>" not in text


def test_render_excel_creates_iptt_sheet(tmp_path: Path) -> None:
    flags = pd.DataFrame({"row_index": [1], "column": ["age"], "reason": ["outlier"]})
    out = render_excel(SAMPLE_RESULTS, tmp_path / "iptt.xlsx", quality_flags=flags)
    wb = load_workbook(out)
    assert "IPTT" in wb.sheetnames
    assert "Disaggregation" in wb.sheetnames
    assert "Quality flags" in wb.sheetnames
    assert "Metadata" in wb.sheetnames
    iptt = wb["IPTT"]
    assert iptt.cell(row=1, column=1).value == "Code"
    assert iptt.cell(row=2, column=1).value == "OC1.1"


def test_render_excel_sanitises_formula_cells(tmp_path: Path) -> None:
    hostile = {
        **SAMPLE_RESULTS,
        "indicators": [
            {
                **SAMPLE_RESULTS["indicators"][0],
                "name": "=HYPERLINK('http://evil')",
            }
        ],
    }
    out = render_excel(hostile, tmp_path / "iptt.xlsx")
    wb = load_workbook(out)
    name_cell = wb["IPTT"].cell(row=2, column=2).value
    assert isinstance(name_cell, str)
    assert name_cell.startswith("'=")


def test_render_report_pipeline_round_trip(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(SAMPLE_RESULTS))
    out_dir = tmp_path / "out"
    html = render_report(
        project_dir=tmp_path,
        results_json=results_path,
        out_dir=out_dir,
        open_report=False,
    )
    assert html.exists()
    assert (out_dir / "iptt.xlsx").exists()
