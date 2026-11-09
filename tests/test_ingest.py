"""Tests for zyuka.ingest.* on synthetic fixtures only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from zyuka.errors import IngestError
from zyuka.ingest.kobo import (
    normalise_select_multiple,
    read_kobo_csv,
    read_kobo_xlsx,
    strip_group_prefixes,
)
from zyuka.ingest.odk import read_odk_csv
from zyuka.ingest.rounds import load_round, load_rounds, read_table
from zyuka.ingest.xlsform import UnsupportedExpression, parse_xlsform, translate_expression


def _write_csv(path: Path, df: pd.DataFrame) -> Path:
    df.to_csv(path, index=False)
    return path


def test_read_kobo_csv_round_trip(tmp_path: Path) -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = _write_csv(tmp_path / "s.csv", df)
    out = read_kobo_csv(path)
    pd.testing.assert_frame_equal(out, df)


def test_read_kobo_csv_missing_file(tmp_path: Path) -> None:
    with pytest.raises(IngestError):
        read_kobo_csv(tmp_path / "missing.csv")


def test_strip_group_prefixes_simple() -> None:
    df = pd.DataFrame({"group_x/age": [1], "group_x/sex": ["f"], "raw": [0]})
    out = strip_group_prefixes(df)
    assert list(out.columns) == ["age", "sex", "raw"]


def test_strip_group_prefixes_handles_collisions() -> None:
    df = pd.DataFrame({"g1/name": ["a"], "g2/name": ["b"]})
    out = strip_group_prefixes(df)
    assert list(out.columns) == ["name", "name__2"]
    assert out["name"].iloc[0] == "a"
    assert out["name__2"].iloc[0] == "b"


def test_normalise_select_multiple_detects_onehot() -> None:
    df = pd.DataFrame(
        {
            "services/health": [1, 0, 1],
            "services/education": [1, 1, 0],
            "services/wash": [0, 0, 0],
            "age": [10, 20, 30],
        }
    )
    out = normalise_select_multiple(df)
    assert "services" in out.columns
    assert "services/health" not in out.columns
    assert out["services"].tolist() == ["health education", "education", "health"]
    assert "age" in out.columns  # non-grouped columns preserved


def test_read_kobo_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "data.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["a", "b"])
    ws.append([1, "x"])
    ws.append([2, "y"])
    wb.save(path)
    out = read_kobo_xlsx(path)
    assert list(out.columns) == ["a", "b"]
    assert out["a"].tolist() == [1, 2]


def test_read_odk_csv_synthesises_uuid(tmp_path: Path) -> None:
    df = pd.DataFrame({"instanceID": ["uuid:abc", "uuid:def"], "age": [1, 2]})
    path = _write_csv(tmp_path / "odk.csv", df)
    out = read_odk_csv(path)
    assert "_uuid" in out.columns
    assert out["_uuid"].tolist() == ["abc", "def"]


def test_read_table_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "data.sav"
    bad.write_text("not supported")
    with pytest.raises(IngestError):
        read_table(bad)


def test_load_round_tags_and_strips(tmp_path: Path) -> None:
    df = pd.DataFrame({"group_x/age": [10, 20]})
    path = _write_csv(tmp_path / "s.csv", df)
    out = load_round(path, "baseline")
    assert "age" in out.columns
    assert (out["round"] == "baseline").all()


def test_load_rounds(tmp_path: Path) -> None:
    for name in ("baseline", "midline"):
        _write_csv(tmp_path / f"{name}.csv", pd.DataFrame({"age": [1, 2]}))
    paths = {
        "baseline": tmp_path / "baseline.csv",
        "midline": tmp_path / "midline.csv",
    }
    rounds = load_rounds(paths)
    assert set(rounds) == {"baseline", "midline"}
    assert (rounds["baseline"]["round"] == "baseline").all()


def test_translate_expression_basic() -> None:
    out = translate_expression("${age} >= 18 and ${sex} = 'f'")
    assert "`age`" in out and ">=" in out and "==" in out and "'f'" in out


def test_translate_expression_dot_uses_current_field() -> None:
    out = translate_expression(". != ''", current_field="consent")
    assert "`consent`" in out


def test_translate_expression_rejects_unsupported() -> None:
    with pytest.raises(UnsupportedExpression):
        translate_expression("count-selected(${services}) > 0")


def test_parse_xlsform(tmp_path: Path) -> None:
    path = tmp_path / "form.xlsx"
    wb = Workbook()
    survey = wb.active
    assert survey is not None
    survey.title = "survey"
    survey.append(["type", "name", "label", "constraint", "relevant"])
    survey.append(["integer", "age", "Age", ". >= 0 and . <= 120", None])
    survey.append(["select_one sex_choices", "sex", "Sex", None, None])
    choices = wb.create_sheet("choices")
    choices.append(["list_name", "name", "label"])
    choices.append(["sex_choices", "f", "Female"])
    choices.append(["sex_choices", "m", "Male"])
    wb.save(path)

    form = parse_xlsform(path)
    assert "age" in form.questions
    assert form.questions["sex"].choice_list == "sex_choices"
    assert form.label_for("sex", "f") == "Female"
    assert form.questions["age"].constraint == ". >= 0 and . <= 120"
