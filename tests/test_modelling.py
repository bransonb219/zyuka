"""Tests for zyuka.analysis.modelling (Phase 2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from zyuka.analysis.modelling import (
    breusch_pagan_heteroskedasticity,
    classify_with_cv,
    principal_components,
    profile_clusters,
    variance_inflation_factors,
)


def test_pca_captures_variance_in_fewer_components() -> None:
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, size=200)
    df = pd.DataFrame(
        {
            "a": base,
            "b": base + rng.normal(0, 0.1, size=200),
            "c": base + rng.normal(0, 0.1, size=200),
            "d": rng.normal(0, 1, size=200),
        }
    )
    result = principal_components(df, ["a", "b", "c", "d"])
    # First component should capture most of the shared variance from a,b,c
    assert result.metrics["variance_90pct_components"] <= 3
    assert result.n == 200


def test_vif_flags_collinear_predictor() -> None:
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, size=100)
    df = pd.DataFrame(
        {
            "x1": base,
            "x2": base + rng.normal(0, 0.01, size=100),  # near-perfect collinearity
            "x3": rng.normal(0, 1, size=100),
        }
    )
    result = variance_inflation_factors(df, ["x1", "x2", "x3"])
    assert result.metrics["max_vif"] > 10


def test_breusch_pagan_detects_heteroskedasticity() -> None:
    rng = np.random.default_rng(2)
    x = rng.uniform(0, 10, size=200)
    # Variance grows with x — classic heteroskedasticity
    y = 2 * x + rng.normal(0, 1 + x, size=200)
    df = pd.DataFrame({"y": y, "x": x})
    result = breusch_pagan_heteroskedasticity(df, "y", ["x"])
    assert result.metrics["LM_p_value"] < 0.05


def test_classifier_recovers_signal_for_binary_outcome() -> None:
    rng = np.random.default_rng(3)
    n = 200
    x1 = rng.normal(0, 1, size=n)
    x2 = rng.normal(0, 1, size=n)
    logits = 2 * x1 - x2
    y = (logits > 0).astype(int)
    df = pd.DataFrame({"outcome": y, "x1": x1, "x2": x2})
    result = classify_with_cv(df, "outcome", ["x1", "x2"], cv=3)
    assert result.metrics["best_mean_score"] > 0.8


def test_profile_clusters_returns_centroids_with_sizes() -> None:
    rng = np.random.default_rng(4)
    cluster_a = rng.normal([0, 0], 0.3, size=(60, 2))
    cluster_b = rng.normal([5, 5], 0.3, size=(60, 2))
    cluster_c = rng.normal([-5, 5], 0.3, size=(60, 2))
    df = pd.DataFrame(np.vstack([cluster_a, cluster_b, cluster_c]), columns=["x", "y"])
    result = profile_clusters(df, ["x", "y"], k=3)
    assert result.metrics["k"] == 3
    assert len(result.details["clusters"]) == 3
    assert all("size" in row for row in result.details["clusters"])
