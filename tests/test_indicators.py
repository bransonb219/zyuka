"""Tests for linga.indicators.*."""

from __future__ import annotations

import pandas as pd
import pytest

from linga.config import IndicatorDef, LogframeConfig, OutcomeDef, TrafficLightThresholds
from linga.errors import IndicatorError
from linga.indicators.disaggregate import disaggregate_indicator
from linga.indicators.engine import compute_indicator
from linga.indicators.expressions import evaluate, parse_expression, referenced_columns
from linga.indicators.longitudinal import build_series
from linga.indicators.pipeline import compute_from_rounds
from linga.indicators.validate import validate_logframe

# ---- safe expression parser -------------------------------------------------


def test_parse_rejects_eval_and_attribute_access() -> None:
    with pytest.raises(IndicatorError):
        parse_expression("__import__('os').system('rm -rf /')")
    with pytest.raises(IndicatorError):
        parse_expression("x.something")


def test_parse_rejects_unknown_function() -> None:
    with pytest.raises(IndicatorError):
        parse_expression("foo(x)")


def test_evaluate_basic_comparisons() -> None:
    assert evaluate("sex == 'female'", {"sex": "female"})
    assert not evaluate("sex == 'female'", {"sex": "male"})
    assert evaluate("age >= 18 and age < 65", {"age": 30})
    assert not evaluate("age >= 18 and age < 65", {"age": 10})


def test_evaluate_selected_split() -> None:
    assert evaluate("selected(services, 'wash')", {"services": "health wash"})
    assert not evaluate("selected(services, 'wash')", {"services": "health only"})


def test_evaluate_isna_and_in() -> None:
    assert evaluate("isna(phone)", {"phone": ""})
    assert evaluate("isna(phone)", {"phone": None})
    assert not evaluate("isna(phone)", {"phone": "0977"})
    assert evaluate("sex in ['female', 'male']", {"sex": "female"})
    assert not evaluate("sex in ['female', 'male']", {"sex": "other"})


def test_evaluate_between_and_startswith() -> None:
    assert evaluate("between(age, 18, 65)", {"age": 30})
    assert not evaluate("between(age, 18, 65)", {"age": 80})
    assert evaluate("startswith(code, 'OUT')", {"code": "OUT1.2"})


def test_referenced_columns_ignores_builtins_and_funcs() -> None:
    cols = referenced_columns("selected(services, 'wash') and age > 18")
    assert cols == {"services", "age"}


# ---- engine -----------------------------------------------------------------


def _ind(**kw) -> IndicatorDef:  # type: ignore[no-untyped-def]
    defaults = {
        "code": "T1",
        "name": "Test",
        "type": "count",
        "numerator": "True",
    }
    defaults.update(kw)
    return IndicatorDef(**defaults)


def test_count_indicator() -> None:
    df = pd.DataFrame({"sex": ["female", "male", "female", "male"]})
    result = compute_indicator(df, _ind(numerator="sex == 'female'"))
    assert result.value == 2


def test_count_unique() -> None:
    df = pd.DataFrame({"pid": ["A", "B", "A", "C"]})
    result = compute_indicator(df, _ind(type="count_unique", numerator="pid == pid"))
    assert result.value == 3


def test_proportion() -> None:
    df = pd.DataFrame({"consent": ["yes", "yes", "no", "yes"]})
    result = compute_indicator(
        df,
        _ind(
            type="proportion",
            numerator="consent == 'yes'",
            denominator="True",
        ),
    )
    assert result.value == pytest.approx(0.75)


def test_mean_median_sum() -> None:
    df = pd.DataFrame({"income": [100, 200, 300, 400]})
    assert compute_indicator(df, _ind(type="mean", numerator="income >= 0")).value == 250
    assert compute_indicator(df, _ind(type="median", numerator="income >= 0")).value == 250
    assert compute_indicator(df, _ind(type="sum", numerator="income >= 0")).value == 1000


def test_proportion_with_zero_denominator() -> None:
    df = pd.DataFrame({"consent": ["no", "no"]})
    result = compute_indicator(
        df,
        _ind(
            type="proportion",
            numerator="consent == 'yes'",
            denominator="consent == 'yes'",
        ),
    )
    assert result.value is None
    assert "denominator" in result.note


def test_engine_raises_on_missing_column() -> None:
    df = pd.DataFrame({"age": [30]})
    with pytest.raises(IndicatorError):
        compute_indicator(df, _ind(numerator="foo == 'bar'"))


# ---- disaggregation ---------------------------------------------------------


def test_disaggregate_by_sex() -> None:
    df = pd.DataFrame({"sex": ["female", "male", "female"], "trained": ["yes", "yes", "no"]})
    result = disaggregate_indicator(
        df,
        _ind(
            numerator="trained == 'yes'",
            disaggregations=["sex"],
        ),
    )
    assert result.overall.value == 2
    assert result.by_column["sex"]["female"].value == 1
    assert result.by_column["sex"]["male"].value == 1


# ---- longitudinal -----------------------------------------------------------


def test_build_series_computes_change_and_status() -> None:
    from linga.indicators.engine import IndicatorValue

    ind = _ind(
        type="count",
        numerator="True",
        baseline=10,
        targets={"midline": 20, "endline": 50},
    )
    per_round = {
        "baseline": IndicatorValue("T1", "count", 10, 10, None),
        "midline": IndicatorValue("T1", "count", 18, 18, None),
        "endline": IndicatorValue("T1", "count", 45, 45, None),
    }
    points = build_series(ind, per_round, TrafficLightThresholds(on_track=90, at_risk=50))
    assert points[1].change_from_baseline == 8
    assert points[1].percent_of_target == 90.0
    assert points[1].status == "on_track"
    assert points[2].percent_of_target == 90.0
    assert points[2].status == "on_track"


# ---- validate ---------------------------------------------------------------


def test_validate_catches_missing_column_with_suggestion() -> None:
    logframe = LogframeConfig(
        goal="g",
        goal_indicators=[_ind(code="G1", numerator="household_income > 0")],
    )
    rounds = {"baseline": pd.DataFrame({"household_incom": [1, 2]})}
    result = validate_logframe(logframe, rounds)
    assert not result.ok
    issue = result.issues[0]
    assert "household_income" in issue.message
    assert "household_incom" in issue.suggestion


# ---- pipeline end-to-end on synthetic ---------------------------------------


def test_compute_from_rounds_runs_on_synthetic() -> None:
    from linga.synthetic import SyntheticOptions, generate_round

    rounds = {
        "baseline": generate_round("baseline", SyntheticOptions(rows_per_round=50, seed=1)),
        "midline": generate_round("midline", SyntheticOptions(rows_per_round=50, seed=1)),
    }
    logframe = LogframeConfig(
        goal="Improve wellbeing",
        outcomes=[
            OutcomeDef(
                code="OC1",
                name="Participation",
                indicators=[
                    _ind(
                        code="OC1.1",
                        name="Participants",
                        type="count",
                        numerator="sex == 'female'",
                        disaggregations=["province"],
                        baseline=0,
                        targets={"midline": 30},
                    )
                ],
            )
        ],
    )
    results = compute_from_rounds(logframe, rounds)
    assert results.rounds == ["baseline", "midline"]
    assert results.indicators[0]["code"] == "OC1.1"
    assert "baseline" in results.indicators[0]["per_round"]
    assert len(results.indicators[0]["longitudinal"]) == 2
