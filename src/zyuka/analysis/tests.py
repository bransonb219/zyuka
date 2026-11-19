"""Deterministic wrappers around scipy / statsmodels / scikit-learn.

Each public function returns an :class:`AnalysisResult` with:

* ``name`` and ``kind`` — e.g. ``"Shapiro-Wilk"`` / ``"normality"``
* ``summary`` — a plain-language one-liner for the GUI/CLI
* ``metrics`` — numeric payload (p-values, effect sizes, coefficients)
* ``details`` — structured tables (coefficients, residuals, centroids)

That shape lets the Streamlit page render a uniform card per test
without introspecting library-specific result objects, and lets the CLI
dump everything to JSON for sharing with donors.

The analysis layer never calls the network and only uses locally
installed wheels (scipy, statsmodels, scikit-learn). All inputs are
assumed to be *cleaned* by :mod:`zyuka.quality.remediate`; functions
drop rows with missing values pairwise and surface the effective ``n``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

MIN_GROUP_N = 5
MIN_SHAPIRO_N = 3
MAX_SHAPIRO_N = 5000
MIN_REGRESSION_N = 10


@dataclass
class AnalysisResult:
    """Uniform return type for every statistical test / model."""

    name: str
    kind: str
    columns: list[str] = field(default_factory=list)
    n: int = 0
    summary: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "columns": self.columns,
            "n": self.n,
            "summary": self.summary,
            "metrics": self.metrics,
            "details": self.details,
            "warnings": self.warnings,
        }


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def _significance(p: float, alpha: float = 0.05) -> str:
    return "significant" if p < alpha else "not significant"


# ---------------------------------------------------------------------------
# Normality
# ---------------------------------------------------------------------------


def normality_test(df: pd.DataFrame, column: str) -> AnalysisResult:
    """Shapiro-Wilk + D'Agostino K² on a numeric column.

    Shapiro-Wilk is the default for ``n`` <= 5000; for larger ``n`` it
    becomes overly sensitive, so we add D'Agostino K² (available via
    :func:`scipy.stats.normaltest`) which stays well-behaved at scale.
    """

    series = _numeric_series(df, column).dropna()
    n = len(series)
    result = AnalysisResult(
        name="Normality (Shapiro-Wilk + D'Agostino K²)",
        kind="normality",
        columns=[column],
        n=n,
    )
    if n < MIN_SHAPIRO_N:
        result.warnings.append(f"Need at least {MIN_SHAPIRO_N} values; got {n}.")
        result.summary = "Not enough data for a normality test."
        return result
    sw_sample = series if n <= MAX_SHAPIRO_N else series.sample(MAX_SHAPIRO_N, random_state=42)
    sw_stat, sw_p = stats.shapiro(sw_sample)
    try:
        k2_stat, k2_p = stats.normaltest(series)
    except ValueError:
        k2_stat, k2_p = float("nan"), float("nan")
    result.metrics = {
        "shapiro_W": float(sw_stat),
        "shapiro_p": float(sw_p),
        "dagostino_K2": float(k2_stat) if k2_stat == k2_stat else 0.0,
        "dagostino_p": float(k2_p) if k2_p == k2_p else 1.0,
        "skew": float(stats.skew(series)),
        "kurtosis": float(stats.kurtosis(series)),
    }
    verdict = "Normal" if sw_p >= 0.05 else "Non-normal"
    result.summary = (
        f"{verdict} at α=0.05 (Shapiro-Wilk W={sw_stat:.3f}, p={sw_p:.4f}; "
        f"skew={result.metrics['skew']:.2f}, kurt={result.metrics['kurtosis']:.2f})."
    )
    return result


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


def pearson_correlation(df: pd.DataFrame, a: str, b: str) -> AnalysisResult:
    """Pearson r on two numeric columns (pairwise complete)."""

    pair = pd.DataFrame({a: _numeric_series(df, a), b: _numeric_series(df, b)}).dropna()
    n = len(pair)
    result = AnalysisResult(name="Pearson correlation", kind="correlation", columns=[a, b], n=n)
    if n < MIN_GROUP_N:
        result.summary = f"Too few paired observations ({n})."
        return result
    r, p = stats.pearsonr(pair[a], pair[b])
    result.metrics = {"r": float(r), "p": float(p), "r2": float(r * r)}
    strength = _correlation_strength(abs(r))
    result.summary = (
        f"{strength} {_direction(r)} linear relationship (r={r:.3f}, p={p:.4f}, n={n})."
    )
    return result


def spearman_correlation(df: pd.DataFrame, a: str, b: str) -> AnalysisResult:
    """Spearman ρ on two numeric or ordinal columns."""

    pair = pd.DataFrame({a: _numeric_series(df, a), b: _numeric_series(df, b)}).dropna()
    n = len(pair)
    result = AnalysisResult(name="Spearman correlation", kind="correlation", columns=[a, b], n=n)
    if n < MIN_GROUP_N:
        result.summary = f"Too few paired observations ({n})."
        return result
    rho, p = stats.spearmanr(pair[a], pair[b])
    result.metrics = {"rho": float(rho), "p": float(p)}
    strength = _correlation_strength(abs(rho))
    result.summary = (
        f"{strength} {_direction(rho)} monotonic relationship (ρ={rho:.3f}, p={p:.4f}, n={n})."
    )
    return result


def pairwise_correlations(
    df: pd.DataFrame,
    columns: Sequence[str] | None = None,
    method: str = "pearson",
    min_n: int = MIN_GROUP_N,
) -> pd.DataFrame:
    """Pairwise correlations across numeric columns; returns long table."""

    cols = list(columns) if columns else list(df.select_dtypes(include="number").columns)
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            pair = pd.DataFrame({a: _numeric_series(df, a), b: _numeric_series(df, b)}).dropna()
            if len(pair) < min_n:
                continue
            if pair[a].std(ddof=1) == 0 or pair[b].std(ddof=1) == 0:
                continue
            if method == "spearman":
                stat, p = stats.spearmanr(pair[a], pair[b])
            else:
                stat, p = stats.pearsonr(pair[a], pair[b])
            rows.append({"a": a, "b": b, "coef": float(stat), "p": float(p), "n": len(pair)})
    if not rows:
        return pd.DataFrame(columns=["a", "b", "coef", "p", "n"])
    return pd.DataFrame(rows).sort_values("coef", key=lambda s: s.abs(), ascending=False)


def _direction(r: float) -> str:
    if r >= 0:
        return "positive"
    return "negative"


def _correlation_strength(abs_r: float) -> str:
    if abs_r < 0.1:
        return "Negligible"
    if abs_r < 0.3:
        return "Weak"
    if abs_r < 0.5:
        return "Moderate"
    if abs_r < 0.7:
        return "Strong"
    return "Very strong"


# ---------------------------------------------------------------------------
# Reliability (Cronbach's alpha)
# ---------------------------------------------------------------------------


def cronbach_alpha(df: pd.DataFrame, columns: Sequence[str]) -> AnalysisResult:
    """Cronbach's α reliability coefficient across ``columns`` (items).

    Returns NaN with a warning if any item has zero variance or fewer
    than two items are supplied.
    """

    cols = list(columns)
    result = AnalysisResult(name="Cronbach's α", kind="reliability", columns=cols)
    if len(cols) < 2:
        result.warnings.append("Need at least 2 items for α.")
        result.summary = "At least two items are needed to compute reliability."
        return result
    items = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    n_items = len(cols)
    n_obs = len(items)
    result.n = n_obs
    if n_obs < MIN_GROUP_N:
        result.summary = f"Too few complete rows ({n_obs})."
        return result
    item_variances = items.var(ddof=1)
    total = items.sum(axis=1)
    total_variance = float(total.var(ddof=1))
    if total_variance == 0:
        result.warnings.append("Scale has zero variance.")
        result.summary = "Items have no variance — reliability is undefined."
        return result
    alpha = float((n_items / (n_items - 1)) * (1 - item_variances.sum() / total_variance))
    result.metrics = {
        "alpha": alpha,
        "items": float(n_items),
        "total_variance": total_variance,
    }
    quality = _alpha_label(alpha)
    result.summary = f"α = {alpha:.3f} across {n_items} items ({quality}; n={n_obs})."
    return result


def _alpha_label(alpha: float) -> str:
    if alpha >= 0.9:
        return "excellent"
    if alpha >= 0.8:
        return "good"
    if alpha >= 0.7:
        return "acceptable"
    if alpha >= 0.6:
        return "questionable"
    return "poor"


# ---------------------------------------------------------------------------
# Group comparisons
# ---------------------------------------------------------------------------


def t_test_independent(
    df: pd.DataFrame, value_column: str, group_column: str, equal_var: bool = False
) -> AnalysisResult:
    """Welch's t-test (``equal_var=False`` by default) between two groups."""

    groups = _split_groups(df, value_column, group_column, expected=2)
    name = "Welch's t-test" if not equal_var else "Student's t-test"
    result = AnalysisResult(
        name=name,
        kind="group_difference",
        columns=[value_column, group_column],
    )
    if len(groups) != 2:
        result.summary = f"{group_column!r} must have exactly 2 groups ≥ {MIN_GROUP_N}."
        return result
    (label_a, a), (label_b, b) = groups
    result.n = int(len(a) + len(b))
    t, p = stats.ttest_ind(a, b, equal_var=equal_var)
    effect = _cohens_d(a, b)
    result.metrics = {
        "t": float(t),
        "p": float(p),
        "cohens_d": float(effect),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "n_a": float(len(a)),
        "n_b": float(len(b)),
    }
    result.details["groups"] = {str(label_a): len(a), str(label_b): len(b)}
    result.summary = (
        f"Means {label_a}={np.mean(a):.3f} vs {label_b}={np.mean(b):.3f} — "
        f"{_significance(p)} (t={t:.3f}, p={p:.4f}, d={effect:.2f})."
    )
    return result


def mann_whitney_u(df: pd.DataFrame, value_column: str, group_column: str) -> AnalysisResult:
    """Mann-Whitney U — non-parametric two-group comparison."""

    groups = _split_groups(df, value_column, group_column, expected=2)
    result = AnalysisResult(
        name="Mann-Whitney U",
        kind="group_difference",
        columns=[value_column, group_column],
    )
    if len(groups) != 2:
        result.summary = f"{group_column!r} must have exactly 2 groups ≥ {MIN_GROUP_N}."
        return result
    (label_a, a), (label_b, b) = groups
    result.n = int(len(a) + len(b))
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    result.metrics = {
        "U": float(u),
        "p": float(p),
        "median_a": float(np.median(a)),
        "median_b": float(np.median(b)),
    }
    result.details["groups"] = {str(label_a): len(a), str(label_b): len(b)}
    result.summary = (
        f"Medians {label_a}={np.median(a):.3f} vs {label_b}={np.median(b):.3f} — "
        f"{_significance(p)} (U={u:.1f}, p={p:.4f})."
    )
    return result


def oneway_anova(df: pd.DataFrame, value_column: str, group_column: str) -> AnalysisResult:
    """One-way ANOVA across ≥ 3 groups on a numeric column."""

    groups = _split_groups(df, value_column, group_column, min_groups=3)
    result = AnalysisResult(
        name="One-way ANOVA",
        kind="group_difference",
        columns=[value_column, group_column],
    )
    if len(groups) < 3:
        result.summary = f"Need ≥ 3 groups of size ≥ {MIN_GROUP_N} in {group_column!r}."
        return result
    arrays = [arr for _, arr in groups]
    result.n = int(sum(len(a) for a in arrays))
    f_stat, p = stats.f_oneway(*arrays)
    eta_sq = _eta_squared(arrays)
    result.metrics = {"F": float(f_stat), "p": float(p), "eta_squared": float(eta_sq)}
    result.details["groups"] = {str(label): len(arr) for label, arr in groups}
    result.summary = (
        f"{len(groups)} groups — {_significance(p)} (F={f_stat:.3f}, p={p:.4f}, η²={eta_sq:.3f})."
    )
    return result


def kruskal_wallis(df: pd.DataFrame, value_column: str, group_column: str) -> AnalysisResult:
    """Kruskal-Wallis H — non-parametric ANOVA for ≥ 3 groups."""

    groups = _split_groups(df, value_column, group_column, min_groups=3)
    result = AnalysisResult(
        name="Kruskal-Wallis H",
        kind="group_difference",
        columns=[value_column, group_column],
    )
    if len(groups) < 3:
        result.summary = f"Need ≥ 3 groups of size ≥ {MIN_GROUP_N} in {group_column!r}."
        return result
    arrays = [arr for _, arr in groups]
    result.n = int(sum(len(a) for a in arrays))
    h_stat, p = stats.kruskal(*arrays)
    result.metrics = {"H": float(h_stat), "p": float(p)}
    result.details["groups"] = {str(label): len(arr) for label, arr in groups}
    result.summary = f"{len(groups)} groups — {_significance(p)} (H={h_stat:.3f}, p={p:.4f})."
    return result


def _split_groups(
    df: pd.DataFrame,
    value_column: str,
    group_column: str,
    *,
    expected: int | None = None,
    min_groups: int = 2,
) -> list[tuple[str, np.ndarray]]:
    """Split values by group, keeping only groups with ≥ ``MIN_GROUP_N`` points."""

    if value_column not in df.columns or group_column not in df.columns:
        return []
    values = _numeric_series(df, value_column)
    groups: list[tuple[str, np.ndarray]] = []
    for label, chunk in df.assign(__v=values).groupby(group_column, dropna=True):
        clean = chunk["__v"].dropna()
        if len(clean) < MIN_GROUP_N:
            continue
        groups.append((str(label), clean.to_numpy()))
    if expected is not None and len(groups) != expected:
        return groups
    if len(groups) < min_groups:
        return groups
    return groups


def _cohens_d(a: Iterable[float], b: Iterable[float]) -> float:
    a_arr = np.asarray(list(a), dtype=float)
    b_arr = np.asarray(list(b), dtype=float)
    if len(a_arr) < 2 or len(b_arr) < 2:
        return 0.0
    pooled = np.sqrt(
        ((len(a_arr) - 1) * a_arr.var(ddof=1) + (len(b_arr) - 1) * b_arr.var(ddof=1))
        / (len(a_arr) + len(b_arr) - 2)
    )
    if pooled == 0:
        return 0.0
    return float((a_arr.mean() - b_arr.mean()) / pooled)


def _eta_squared(arrays: Sequence[np.ndarray]) -> float:
    """η² = SS_between / SS_total."""

    all_values = np.concatenate(arrays)
    grand_mean = all_values.mean()
    ss_between = sum(len(arr) * (arr.mean() - grand_mean) ** 2 for arr in arrays)
    ss_total = ((all_values - grand_mean) ** 2).sum()
    if ss_total == 0:
        return 0.0
    return float(ss_between / ss_total)


# ---------------------------------------------------------------------------
# Chi-square / Fisher's exact
# ---------------------------------------------------------------------------


def two_way_chi_square(df: pd.DataFrame, a: str, b: str) -> AnalysisResult:
    """χ² test of independence; falls back to Fisher's exact on a 2×2 with small cells."""

    name = "χ² test of independence"
    result = AnalysisResult(name=name, kind="association", columns=[a, b])
    if a not in df.columns or b not in df.columns:
        result.summary = "One of the columns is missing."
        return result
    table = pd.crosstab(df[a], df[b])
    if table.shape[0] < 2 or table.shape[1] < 2:
        result.summary = "Both variables need at least two categories."
        return result
    result.n = int(table.values.sum())
    chi2, p, dof, expected = stats.chi2_contingency(table)
    small_expected = int((expected < 5).sum())
    use_fisher = table.shape == (2, 2) and small_expected > 0
    if use_fisher:
        odds, p_fisher = stats.fisher_exact(table.values)
        result.name = "Fisher's exact (2×2)"
        result.metrics = {
            "chi2": float(chi2),
            "fisher_p": float(p_fisher),
            "odds_ratio": float(odds),
            "dof": float(dof),
        }
        result.summary = f"{result.name}: p={p_fisher:.4f}, odds ratio={odds:.2f} (n={result.n})."
    else:
        cramer_v = _cramers_v(chi2, result.n, table.shape)
        result.metrics = {
            "chi2": float(chi2),
            "p": float(p),
            "dof": float(dof),
            "cramers_v": float(cramer_v),
        }
        result.summary = (
            f"χ²({int(dof)})={chi2:.3f}, p={p:.4f}, Cramér's V={cramer_v:.2f}, n={result.n}."
        )
    result.details["table"] = table.to_dict()
    result.details["small_expected_cells"] = small_expected
    return result


def _cramers_v(chi2: float, n: int, shape: tuple[int, int]) -> float:
    if n == 0:
        return 0.0
    k = min(shape) - 1
    if k <= 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * k)))


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


def ordinary_least_squares(
    df: pd.DataFrame,
    outcome: str,
    predictors: Sequence[str],
) -> AnalysisResult:
    """OLS regression of ``outcome`` on ``predictors`` (numeric only).

    Returns coefficients, standard errors, p-values, R², adjusted R² and
    the F statistic. Categorical predictors should be dummy-encoded by
    the caller before passing in — we keep this function dependency-free
    of design matrices to make the GUI predictable.
    """

    import statsmodels.api as sm

    cols = [outcome, *predictors]
    frame = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(name="OLS regression", kind="regression", columns=cols)
    if len(frame) < MIN_REGRESSION_N:
        result.summary = f"Need at least {MIN_REGRESSION_N} complete rows; got {len(frame)}."
        return result
    y = frame[outcome].astype(float).to_numpy()
    x = sm.add_constant(frame[list(predictors)].astype(float), has_constant="add")
    model = sm.OLS(y, x).fit()
    result.n = len(frame)
    result.metrics = {
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "f_statistic": float(model.fvalue),
        "f_p_value": float(model.f_pvalue),
    }
    coefs: list[dict[str, Any]] = []
    for name, coef in model.params.items():
        coefs.append(
            {
                "variable": str(name),
                "coef": float(coef),
                "std_err": float(model.bse.get(name, float("nan"))),
                "t": float(model.tvalues.get(name, float("nan"))),
                "p": float(model.pvalues.get(name, float("nan"))),
            }
        )
    result.details["coefficients"] = coefs
    sig_predictors = [
        c["variable"] for c in coefs if c["variable"] != "const" and float(c["p"]) < 0.05
    ]
    result.summary = (
        f"R²={model.rsquared:.3f}, adj R²={model.rsquared_adj:.3f}, F p={model.f_pvalue:.4f}; "
        f"{len(sig_predictors)}/{len(predictors)} predictor(s) significant at α=0.05."
    )
    return result


# ---------------------------------------------------------------------------
# Covariance
# ---------------------------------------------------------------------------


def sample_covariance(df: pd.DataFrame, columns: Sequence[str]) -> AnalysisResult:
    """Covariance matrix across ``columns`` using pairwise complete rows."""

    cols = list(columns)
    result = AnalysisResult(name="Sample covariance", kind="covariance", columns=cols)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result.n = len(numeric)
    if result.n < MIN_GROUP_N or len(cols) < 2:
        result.summary = "Need at least 5 complete rows and 2 columns."
        return result
    cov = numeric.cov()
    result.details["matrix"] = cov.to_dict()
    diag = cov.values.diagonal()
    result.metrics = {"mean_variance": float(np.mean(diag))}
    result.summary = f"Covariance matrix ({cov.shape[0]}×{cov.shape[1]}) on n={result.n}."
    return result


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def kmeans_cluster(
    df: pd.DataFrame,
    columns: Sequence[str],
    k_min: int = 2,
    k_max: int = 6,
    random_state: int = 42,
) -> AnalysisResult:
    """K-means over numeric ``columns``; picks k by silhouette score."""

    cols = list(columns)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(name="K-means clustering", kind="clustering", columns=cols)
    result.n = len(numeric)
    if result.n < max(k_max * 2, MIN_GROUP_N * 2) or len(cols) < 2:
        result.summary = "Need at least 2 columns and 20+ complete rows."
        return result
    scaler = StandardScaler()
    scaled = scaler.fit_transform(numeric.to_numpy())
    k_max = min(k_max, result.n - 1)
    scores: list[dict[str, float]] = []
    best = None
    for k in range(k_min, k_max + 1):
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = model.fit_predict(scaled)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(scaled, labels))
        scores.append({"k": float(k), "silhouette": score, "inertia": float(model.inertia_)})
        if best is None or score > best["silhouette"]:
            best = {"k": k, "silhouette": score, "labels": labels, "inertia": model.inertia_}
    if best is None:
        result.summary = "Could not fit any clustering solution."
        return result
    centroids_scaled = (
        KMeans(n_clusters=best["k"], random_state=random_state, n_init=10)
        .fit(scaled)
        .cluster_centers_
    )
    centroids = pd.DataFrame(
        scaler.inverse_transform(centroids_scaled),
        columns=cols,
    )
    centroids["cluster"] = centroids.index
    centroids["size"] = [int(np.sum(best["labels"] == i)) for i in range(best["k"])]
    result.metrics = {
        "best_k": float(best["k"]),
        "silhouette": float(best["silhouette"]),
        "inertia": float(best["inertia"]),
    }
    result.details["scores"] = scores
    result.details["centroids"] = centroids.to_dict(orient="records")
    result.summary = (
        f"Best k={best['k']} (silhouette={best['silhouette']:.3f}) across {len(cols)} features."
    )
    return result


# ---------------------------------------------------------------------------
# Convenience bundle
# ---------------------------------------------------------------------------


def run_many(df: pd.DataFrame, suggestions: Iterable[Mapping[str, Any]]) -> list[AnalysisResult]:
    """Execute a list of advisor suggestions (as mappings) and return results.

    Each suggestion dict is ``{"test": name, "columns": [...]}``. Unknown
    names are skipped silently so the UI can stay forward-compatible.
    """

    from zyuka.analysis.modelling import (
        breusch_pagan_heteroskedasticity,
        classify_with_cv,
        principal_components,
        profile_clusters,
        variance_inflation_factors,
    )

    dispatch = {
        "normality": lambda s: normality_test(df, s["columns"][0]),
        "pearson": lambda s: pearson_correlation(df, s["columns"][0], s["columns"][1]),
        "spearman": lambda s: spearman_correlation(df, s["columns"][0], s["columns"][1]),
        "cronbach_alpha": lambda s: cronbach_alpha(df, s["columns"]),
        "t_test": lambda s: t_test_independent(df, s["columns"][0], s["columns"][1]),
        "mann_whitney": lambda s: mann_whitney_u(df, s["columns"][0], s["columns"][1]),
        "anova": lambda s: oneway_anova(df, s["columns"][0], s["columns"][1]),
        "kruskal": lambda s: kruskal_wallis(df, s["columns"][0], s["columns"][1]),
        "chi_square": lambda s: two_way_chi_square(df, s["columns"][0], s["columns"][1]),
        "ols": lambda s: ordinary_least_squares(df, s["columns"][0], s["columns"][1:]),
        "covariance": lambda s: sample_covariance(df, s["columns"]),
        "kmeans": lambda s: kmeans_cluster(df, s["columns"]),
        "pca": lambda s: principal_components(df, s["columns"]),
        "vif": lambda s: variance_inflation_factors(df, s["columns"]),
        "breusch_pagan": lambda s: breusch_pagan_heteroskedasticity(
            df, s["columns"][0], s["columns"][1:]
        ),
        "classifier": lambda s: classify_with_cv(df, s["columns"][0], s["columns"][1:]),
        "cluster_profile": lambda s: profile_clusters(df, s["columns"]),
    }
    results: list[AnalysisResult] = []
    for suggestion in suggestions:
        fn = dispatch.get(str(suggestion.get("test", "")))
        if fn is None:
            continue
        try:
            results.append(fn(suggestion))
        except (ValueError, KeyError, TypeError) as exc:
            results.append(
                AnalysisResult(
                    name=str(suggestion.get("test", "")),
                    kind="error",
                    columns=list(suggestion.get("columns", [])),
                    summary=f"Could not run: {exc}",
                )
            )
    return results
