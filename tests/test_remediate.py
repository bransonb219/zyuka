"""Tests for zyuka.quality.remediate and zyuka.quality.rules."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from zyuka.quality.remediate import (
    CleaningDecision,
    FixAction,
    apply_decisions,
    drop_duplicate_rows,
    drop_rows,
    impute_median,
    impute_mode,
    nullify_cells,
    propose_actions,
    winsorize,
)
from zyuka.quality.report import run_quality
from zyuka.quality.rules import (
    CleaningRule,
    CleaningRules,
    load_rules,
    preapproved_decisions,
    save_rules,
)

# ---------------------------------------------------------------------------
# Pure fix functions
# ---------------------------------------------------------------------------


def test_drop_duplicate_rows_keeps_most_complete() -> None:
    df = pd.DataFrame(
        {
            "_uuid": ["a", "a", "b"],
            "x": [1, None, 3],
            "y": [10, None, 30],
        }
    )
    cleaned, dropped = drop_duplicate_rows(df, rows=[0, 1], key_column="_uuid")
    assert dropped == 1
    assert len(cleaned) == 2
    # Row 0 is more complete than row 1, so it should remain.
    assert 0 in cleaned.index and 1 not in cleaned.index


def test_impute_mode_fills_blanks() -> None:
    df = pd.DataFrame({"sex": ["F", "M", None, "F", ""]})
    cleaned, filled = impute_mode(df, "sex")
    assert filled == 2
    assert cleaned["sex"].isna().sum() == 0
    assert (cleaned["sex"] == "F").sum() == 4


def test_impute_median_fills_blanks_with_median() -> None:
    df = pd.DataFrame({"age": [10, 20, None, 40, None]})
    cleaned, filled = impute_median(df, "age")
    assert filled == 2
    assert pd.to_numeric(cleaned["age"]).median() == 20


def test_drop_rows_removes_specified() -> None:
    df = pd.DataFrame({"x": [1, 2, 3, 4]})
    cleaned, n = drop_rows(df, rows=[1, 3])
    assert n == 2
    assert cleaned["x"].tolist() == [1, 3]


def test_winsorize_caps_outliers_and_keeps_row_count() -> None:
    df = pd.DataFrame({"val": [*range(100), 10_000]})
    before = len(df)
    cleaned, affected = winsorize(df, "val", p_low=0.01, p_high=0.99)
    assert len(cleaned) == before
    assert affected >= 1
    assert cleaned["val"].max() < 10_000


def test_nullify_cells_blanks_without_dropping() -> None:
    df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    cleaned, n = nullify_cells(df, "y", rows=[0, 2])
    assert n == 2
    assert len(cleaned) == 3
    assert pd.isna(cleaned.loc[0, "y"]) and pd.isna(cleaned.loc[2, "y"])
    assert cleaned.loc[1, "y"] == "b"


# ---------------------------------------------------------------------------
# Proposal engine
# ---------------------------------------------------------------------------


def test_propose_actions_maps_outlier_to_winsorize() -> None:
    df = pd.DataFrame({"age": [20, 22, 25, 999]})
    flags = pd.DataFrame([{"row_index": 3, "column": "age", "reason": "outlier (iqr)"}])
    actions = propose_actions(df, flags)
    assert len(actions) == 1
    assert actions[0].kind == "winsorize"
    assert actions[0].column == "age"


def test_propose_actions_maps_duplicate_to_drop() -> None:
    df = pd.DataFrame({"_uuid": ["a", "a", "b"]})
    flags = pd.DataFrame(
        [
            {"row_index": 0, "column": "_uuid", "reason": "duplicate _uuid"},
            {"row_index": 1, "column": "_uuid", "reason": "duplicate _uuid"},
        ]
    )
    actions = propose_actions(df, flags)
    assert any(a.kind == "drop_duplicate_rows" for a in actions)


def test_propose_actions_adds_missingness_proposal() -> None:
    df = pd.DataFrame({"age": [20, 22, None, None, None]})
    per_col = pd.DataFrame([{"column": "age", "missing": 3, "pct": 60.0}])
    actions = propose_actions(
        df, pd.DataFrame(columns=["row_index", "column", "reason"]), per_column_missing=per_col
    )
    assert len(actions) == 1
    assert actions[0].kind == "impute_median"
    assert actions[0].reason == "missingness"


# ---------------------------------------------------------------------------
# Apply loop
# ---------------------------------------------------------------------------


def test_apply_decisions_respects_rejects() -> None:
    df = pd.DataFrame({"age": [20, 22, 999]})
    action = FixAction(
        kind="winsorize",
        reason="outlier (iqr)",
        column="age",
        row_indices=(2,),
        params={"p_low": 0.01, "p_high": 0.99},
    )
    decision = CleaningDecision(action=action, status="rejected")
    result = apply_decisions(df, [decision])
    assert result.cleaned["age"].max() == 999
    assert not result.applied


def test_apply_decisions_end_to_end_on_synthetic() -> None:
    df = pd.DataFrame(
        {
            "_uuid": ["a", "a", "b", "c"],
            "age": [20, 22, 25, 9999],
            "sex": ["F", "M", None, "M"],
        }
    )
    quality = run_quality(df, numeric_outlier_cols=["age"])
    actions = propose_actions(df, quality.flags, quality.per_column_missing)
    decisions = [CleaningDecision(action=a, status="approved") for a in actions]
    result = apply_decisions(df, decisions)
    assert len(result.cleaned) <= len(df)
    # Winsorisation should have knocked the 9999 down.
    assert pd.to_numeric(result.cleaned["age"]).max() < 9999


# ---------------------------------------------------------------------------
# Rule memory
# ---------------------------------------------------------------------------


def test_rules_round_trip(tmp_path: Path) -> None:
    rules = CleaningRules(
        rules=[
            CleaningRule(
                reason="outlier (iqr)",
                column="age",
                kind="winsorize",
                params={"p_low": 0.01, "p_high": 0.99},
                approved_at="2026-11-19T10:00:00+00:00",
            )
        ]
    )
    save_rules(tmp_path, rules)
    loaded = load_rules(tmp_path)
    assert len(loaded.rules) == 1
    assert loaded.rules[0].column == "age"
    assert loaded.rules[0].kind == "winsorize"


def test_rules_upsert_increments_count() -> None:
    rules = CleaningRules()
    action = FixAction(
        kind="winsorize",
        reason="outlier (iqr)",
        column="age",
        row_indices=(0,),
        params={"p_low": 0.01, "p_high": 0.99},
    )
    d1 = CleaningDecision(action=action, status="approved")
    rules.upsert(d1)
    rules.upsert(d1)
    assert len(rules.rules) == 1
    assert rules.rules[0].approved_count == 2


def test_preapproved_decisions_matches_saved_rule() -> None:
    rules = CleaningRules(
        rules=[
            CleaningRule(
                reason="outlier (iqr)",
                column="age",
                kind="winsorize",
                params={"p_low": 0.01, "p_high": 0.99},
            )
        ]
    )
    actions = [
        FixAction(
            kind="winsorize",
            reason="outlier (iqr)",
            column="age",
            row_indices=(3,),
            params={"p_low": 0.01, "p_high": 0.99},
        ),
        FixAction(
            kind="nullify_cells",
            reason="constraint violation",
            column="household_income",
            row_indices=(7,),
        ),
    ]
    matched = preapproved_decisions(actions, rules)
    assert len(matched) == 1
    assert matched[0].action.column == "age"
