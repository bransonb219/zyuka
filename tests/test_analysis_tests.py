"""Tests for zyuka.analysis.tests statistical wrappers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from zyuka.analysis.tests import (
    cronbach_alpha,
    kmeans_cluster,
    kruskal_wallis,
    mann_whitney_u,
    normality_test,
    oneway_anova,
    ordinary_least_squares,
    pairwise_correlations,
    pearson_correlation,
    run_many,
    sample_covariance,
    spearman_correlation,
    t_test_independent,
    two_way_chi_square,
)


def test_normality_flags_normal_distribution() -> None:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(0, 1, size=300)})
    result = normality_test(df, "x")
    assert result.metrics["shapiro_p"] > 0.001
    assert "p=" in result.summary


def test_normality_flags_skewed_distribution() -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"x": rng.lognormal(0, 1, size=300)})
    result = normality_test(df, "x")
    assert result.metrics["shapiro_p"] < 0.01


def test_pearson_detects_linear_relationship() -> None:
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, size=200)
    df = pd.DataFrame({"a": a, "b": a * 0.8 + rng.normal(0, 0.3, size=200)})
    result = pearson_correlation(df, "a", "b")
    assert result.metrics["r"] > 0.7
    assert result.metrics["p"] < 0.001


def test_spearman_detects_monotonic_relationship() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8], "b": [1, 2, 4, 8, 16, 32, 64, 128]})
    result = spearman_correlation(df, "a", "b")
    assert result.metrics["rho"] > 0.99


def test_t_test_detects_mean_difference() -> None:
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "value": np.concatenate([rng.normal(10, 2, 80), rng.normal(13, 2, 80)]),
            "group": ["A"] * 80 + ["B"] * 80,
        }
    )
    result = t_test_independent(df, "value", "group")
    assert result.metrics["p"] < 0.001
    assert "d=" in result.summary


def test_mann_whitney_detects_median_shift() -> None:
    rng = np.random.default_rng(4)
    df = pd.DataFrame(
        {
            "value": np.concatenate([rng.exponential(1.0, 60), rng.exponential(2.0, 60)]),
            "group": ["A"] * 60 + ["B"] * 60,
        }
    )
    result = mann_whitney_u(df, "value", "group")
    assert result.metrics["p"] < 0.05


def test_anova_detects_group_mean_diff_across_three_groups() -> None:
    rng = np.random.default_rng(5)
    df = pd.DataFrame(
        {
            "value": np.concatenate(
                [rng.normal(10, 2, 50), rng.normal(12, 2, 50), rng.normal(15, 2, 50)]
            ),
            "group": ["A"] * 50 + ["B"] * 50 + ["C"] * 50,
        }
    )
    result = oneway_anova(df, "value", "group")
    assert result.metrics["p"] < 0.001
    assert result.metrics["eta_squared"] > 0.1


def test_kruskal_detects_rank_diff_across_groups() -> None:
    rng = np.random.default_rng(6)
    df = pd.DataFrame(
        {
            "value": np.concatenate(
                [rng.exponential(1.0, 40), rng.exponential(2.0, 40), rng.exponential(3.0, 40)]
            ),
            "group": ["A"] * 40 + ["B"] * 40 + ["C"] * 40,
        }
    )
    result = kruskal_wallis(df, "value", "group")
    assert result.metrics["p"] < 0.01


def test_chi_square_detects_association() -> None:
    df = pd.DataFrame(
        {
            "a": ["F"] * 50 + ["M"] * 50,
            "b": ["yes"] * 40 + ["no"] * 10 + ["yes"] * 10 + ["no"] * 40,
        }
    )
    result = two_way_chi_square(df, "a", "b")
    assert result.metrics["p"] < 0.001
    assert result.metrics["cramers_v"] > 0.3


def test_chi_square_falls_back_to_fisher_on_small_2x2() -> None:
    df = pd.DataFrame({"a": ["x", "x", "y", "y", "y"], "b": ["p", "q", "p", "q", "q"]})
    result = two_way_chi_square(df, "a", "b")
    assert "Fisher" in result.name


def test_cronbach_alpha_high_on_consistent_items() -> None:
    rng = np.random.default_rng(7)
    base = rng.integers(1, 6, size=200)
    df = pd.DataFrame(
        {
            "q1": np.clip(base + rng.integers(-1, 2, size=200), 1, 5),
            "q2": np.clip(base + rng.integers(-1, 2, size=200), 1, 5),
            "q3": np.clip(base + rng.integers(-1, 2, size=200), 1, 5),
            "q4": np.clip(base + rng.integers(-1, 2, size=200), 1, 5),
        }
    )
    result = cronbach_alpha(df, ["q1", "q2", "q3", "q4"])
    assert result.metrics["alpha"] > 0.6


def test_ols_recovers_positive_slope() -> None:
    rng = np.random.default_rng(8)
    x1 = rng.normal(0, 1, size=200)
    x2 = rng.normal(0, 1, size=200)
    y = 2.0 * x1 - 1.5 * x2 + rng.normal(0, 0.5, size=200)
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})
    result = ordinary_least_squares(df, "y", ["x1", "x2"])
    coefs = {c["variable"]: c["coef"] for c in result.details["coefficients"]}
    assert coefs["x1"] > 1.5
    assert coefs["x2"] < -1.0
    assert result.metrics["r_squared"] > 0.9


def test_covariance_matrix_shape() -> None:
    rng = np.random.default_rng(9)
    df = pd.DataFrame(
        {
            "a": rng.normal(size=100),
            "b": rng.normal(size=100),
            "c": rng.normal(size=100),
        }
    )
    result = sample_covariance(df, ["a", "b", "c"])
    assert result.n == 100
    assert len(result.details["matrix"]) == 3


def test_kmeans_finds_two_clusters_when_data_is_bimodal() -> None:
    rng = np.random.default_rng(10)
    cluster_a = rng.normal(loc=[0, 0], scale=0.3, size=(80, 2))
    cluster_b = rng.normal(loc=[5, 5], scale=0.3, size=(80, 2))
    df = pd.DataFrame(np.vstack([cluster_a, cluster_b]), columns=["x", "y"])
    result = kmeans_cluster(df, ["x", "y"], k_min=2, k_max=4)
    assert result.metrics["best_k"] == 2
    assert result.metrics["silhouette"] > 0.5


def test_pairwise_correlations_returns_sorted_long_table() -> None:
    rng = np.random.default_rng(11)
    base = rng.normal(size=120)
    df = pd.DataFrame(
        {
            "a": base,
            "b": base + rng.normal(0, 0.1, size=120),
            "c": -base + rng.normal(0, 0.1, size=120),
            "d": rng.normal(size=120),
        }
    )
    pairs = pairwise_correlations(df, ["a", "b", "c", "d"])
    assert list(pairs.columns) == ["a", "b", "coef", "p", "n"]
    assert abs(pairs.iloc[0]["coef"]) > 0.9


def test_run_many_dispatches_known_tests() -> None:
    rng = np.random.default_rng(12)
    df = pd.DataFrame(
        {
            "age": rng.integers(18, 70, size=200),
            "income": rng.normal(2500, 800, size=200),
            "sex": rng.choice(["F", "M"], size=200),
        }
    )
    results = run_many(
        df,
        [
            {"test": "normality", "columns": ["income"]},
            {"test": "pearson", "columns": ["age", "income"]},
            {"test": "t_test", "columns": ["income", "sex"]},
            {"test": "unknown", "columns": []},
        ],
    )
    assert len(results) == 3
    assert {r.name for r in results} >= {
        "Pearson correlation",
    }
