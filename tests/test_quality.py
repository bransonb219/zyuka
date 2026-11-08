"""Tests for linga.quality.*."""

from __future__ import annotations

import pandas as pd

from linga.ingest.xlsform import Question, XLSForm
from linga.quality.duplicates import duplicate_identity, duplicate_uuids
from linga.quality.duration import find_duration_issues
from linga.quality.enumerators import enumerator_summary
from linga.quality.missing import missing_per_column, missing_per_enumerator
from linga.quality.outliers import find_outliers, iqr_outliers, zscore_outliers
from linga.quality.report import run_quality
from linga.synthetic import SyntheticOptions, generate_round


def test_duplicate_uuids() -> None:
    df = pd.DataFrame({"_uuid": ["a", "b", "a", "c"]})
    out = duplicate_uuids(df)
    assert len(out) == 2
    assert (out["reason"] == "duplicate _uuid").all()


def test_duplicate_identity_with_date() -> None:
    df = pd.DataFrame(
        {
            "name": ["Alice", "Alice", "Bob"],
            "date": ["2026-01-01", "2026-01-01", "2026-01-02"],
        }
    )
    out = duplicate_identity(df, id_cols=["name"], date_col="date")
    assert len(out) == 2


def test_missing_per_column() -> None:
    df = pd.DataFrame({"a": [1, None, 3], "b": ["", "x", ""]})
    out = missing_per_column(df)
    a_row = out[out["column"] == "a"].iloc[0]
    b_row = out[out["column"] == "b"].iloc[0]
    assert a_row["missing"] == 1
    assert b_row["missing"] == 2


def test_missing_per_enumerator() -> None:
    df = pd.DataFrame(
        {
            "enumerator_id": ["E01", "E01", "E02"],
            "a": [1, None, 3],
            "b": [None, None, 2],
        }
    )
    out = missing_per_enumerator(df)
    assert set(out["enumerator_id"]) == {"E01", "E02"}


def test_iqr_outliers_flag_extremes() -> None:
    s = pd.Series([1, 2, 3, 4, 5, 1000])
    mask = iqr_outliers(s)
    assert mask.iloc[-1]
    assert not mask.iloc[0]


def test_zscore_outliers() -> None:
    s = pd.Series([1.0] * 100 + [50.0])
    mask = zscore_outliers(s, threshold=2.0)
    assert mask.iloc[-1]


def test_find_outliers_in_frame() -> None:
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 1000]})
    out = find_outliers(df, ["x"])
    assert len(out) == 1
    assert out["column"].iloc[0] == "x"


def test_duration_short_interview() -> None:
    df = pd.DataFrame(
        {
            "start": ["2026-01-01T09:00:00", "2026-01-01T10:00:00"],
            "end": ["2026-01-01T09:00:30", "2026-01-01T10:15:00"],
        }
    )
    out = find_duration_issues(df, min_minutes=1.0)
    assert len(out) == 1
    assert "short" in out["reason"].iloc[0]


def test_duration_overnight() -> None:
    df = pd.DataFrame({"start": ["2026-01-01T23:50:00"], "end": ["2026-01-02T00:10:00"]})
    out = find_duration_issues(df, min_minutes=1.0)
    assert any("overnight" in r for r in out["reason"])


def test_enumerator_summary() -> None:
    df = pd.DataFrame(
        {
            "enumerator_id": ["E01", "E01", "E02"],
            "start": ["2026-01-01T09:00", "2026-01-01T10:00", "2026-01-01T11:00"],
            "end": ["2026-01-01T09:10", "2026-01-01T10:15", "2026-01-01T11:20"],
        }
    )
    out = enumerator_summary(df, flagged_row_ids={0})
    e01 = out[out["enumerator_id"] == "E01"].iloc[0]
    assert e01["submissions"] == 2
    assert e01["avg_duration_minutes"] is not None
    assert e01["flag_rate"] == 0.5


def test_run_quality_on_synthetic() -> None:
    df = generate_round("baseline", SyntheticOptions(rows_per_round=50, seed=7))
    report = run_quality(df)
    # Synthetic generator injects a duplicate row + an extreme income.
    assert report.summary["rows"] == len(df)
    assert "duplicate _uuid" in report.summary
    assert any("outlier" in reason for reason in report.summary)
    assert "row_index" in report.flags.columns
    # Never leak PII column values into the flags frame.
    assert set(report.flags.columns) <= {"row_index", "column", "reason"}


def test_run_quality_with_form_catches_constraint() -> None:
    df = pd.DataFrame({"age": [10, 200, 30]})
    form = XLSForm(
        questions={
            "age": Question(
                name="age",
                type="integer",
                label="Age",
                constraint=". >= 0 and . <= 120",
            )
        },
        choices={},
    )
    report = run_quality(df, form=form)
    assert any("constraint" in r for r in report.flags["reason"])
