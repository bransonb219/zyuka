"""Tests for zyuka.analysis.advisor."""

from __future__ import annotations

import numpy as np
import pandas as pd

from zyuka.analysis.advisor import suggest_analyses


def _mearl_frame(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 240
    sex = rng.choice(["F", "M"], size=n)
    district = rng.choice(["Kabwe", "Choma", "Mazabuka", "Monze"], size=n)
    age = rng.integers(18, 70, size=n)
    # Deliberately give income a sex effect so Welch's t-test should fire.
    income = rng.normal(2500 + (sex == "M") * 400, 800, size=n)
    satisfaction = rng.integers(1, 6, size=n)
    trust = rng.integers(1, 6, size=n)
    safety = rng.integers(1, 6, size=n)
    return pd.DataFrame(
        {
            "age": age,
            "income": income,
            "satisfaction": satisfaction,
            "trust": trust,
            "safety": safety,
            "sex": sex,
            "district": district,
        }
    )


def test_advisor_suggests_both_group_comparison_and_correlation() -> None:
    df = _mearl_frame()
    suggestions = suggest_analyses(df)
    tests = {(s.test, tuple(s.columns)) for s in suggestions}
    # Pearson or Spearman on age ↔ income should show up
    assert any(t[0] in {"pearson", "spearman"} for t in tests)
    # Welch's or Mann-Whitney on income by sex should show up
    assert any(
        t[0] in {"t_test", "mann_whitney"} and "income" in t[1] and "sex" in t[1] for t in tests
    )


def test_advisor_proposes_cronbach_on_likert_items() -> None:
    df = _mearl_frame()
    suggestions = suggest_analyses(df)
    cronbach = [s for s in suggestions if s.test == "cronbach_alpha"]
    assert cronbach, "Expected Cronbach's α on satisfaction/trust/safety"
    cols = set(cronbach[0].columns)
    assert {"satisfaction", "trust", "safety"}.issubset(cols)


def test_advisor_proposes_chi_square_for_two_categoricals() -> None:
    df = _mearl_frame()
    suggestions = suggest_analyses(df)
    chi = [s for s in suggestions if s.test == "chi_square"]
    assert chi
    assert {"sex", "district"} == set(chi[0].columns)


def test_advisor_proposes_kmeans_when_multiple_numerics() -> None:
    df = _mearl_frame()
    suggestions = suggest_analyses(df)
    assert any(s.test == "kmeans" for s in suggestions)


def test_advisor_excludes_pii_columns() -> None:
    df = _mearl_frame().assign(phone=["0977" + "123456" * 2] * len(_mearl_frame()))
    suggestions = suggest_analyses(df, pii_columns=["phone"])
    assert not any("phone" in s.columns for s in suggestions)


def test_advisor_returns_empty_for_tiny_frame() -> None:
    df = pd.DataFrame({"x": [1, 2, 3]})
    assert suggest_analyses(df) == []
