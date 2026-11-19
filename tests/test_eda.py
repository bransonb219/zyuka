"""Tests for zyuka.analysis.eda."""

from __future__ import annotations

import numpy as np
import pandas as pd

from zyuka.analysis.eda import profile_dataframe


def _synthetic_frame(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 200
    return pd.DataFrame(
        {
            "age": rng.integers(18, 70, size=n),
            "income": rng.normal(2500, 800, size=n),
            "sex": rng.choice(["F", "M"], size=n, p=[0.55, 0.45]),
            "district": rng.choice(["A", "B", "C", "D"], size=n),
            "feedback": ["Short note"] * (n // 2)
            + ["A longer comment that stretches past twenty-five chars"] * (n - n // 2),
            "started_at": pd.date_range("2026-01-01", periods=n, freq="h"),
        }
    )


def test_profile_classifies_columns_by_kind() -> None:
    df = _synthetic_frame()
    profile = profile_dataframe(df)
    kinds = {c.name: c.kind for c in profile.columns}
    assert kinds["age"] == "numeric"
    assert kinds["income"] == "numeric"
    assert kinds["sex"] == "categorical"
    assert kinds["district"] == "categorical"
    assert kinds["feedback"] == "text"
    assert kinds["started_at"] == "datetime"


def test_numeric_column_has_moments() -> None:
    df = _synthetic_frame()
    profile = profile_dataframe(df)
    income = profile.column("income")
    assert income is not None
    assert income.mean is not None and income.std is not None
    assert income.q1 is not None and income.q3 is not None
    assert income.skew is not None and income.kurtosis is not None


def test_correlations_rank_pairs_by_absolute_r() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, size=150)
    df = pd.DataFrame(
        {
            "a": base,
            "b": base * 0.9 + rng.normal(0, 0.2, size=150),  # strong +
            "c": -base * 0.6 + rng.normal(0, 0.3, size=150),  # moderate -
            "d": rng.normal(0, 1, size=150),  # unrelated
        }
    )
    profile = profile_dataframe(df)
    assert not profile.correlations.empty
    top = profile.correlations.iloc[0]
    assert {top["a"], top["b"]} == {"a", "b"}


def test_profile_counts_duplicate_rows() -> None:
    df = pd.DataFrame({"x": [1, 2, 2, 3], "y": ["a", "b", "b", "c"]})
    profile = profile_dataframe(df)
    assert profile.duplicate_rows == 1
    assert profile.n_rows == 4
    assert profile.n_cols == 2


def test_to_dict_is_json_friendly() -> None:
    df = _synthetic_frame()
    profile = profile_dataframe(df)
    import json

    text = json.dumps(profile.to_dict())
    assert "columns" in text
