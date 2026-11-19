"""Phase 2 analysis — dimensionality reduction, regression diagnostics,
classification and cluster profiling.

These functions sit alongside :mod:`zyuka.analysis.tests`; they're
heavier-weight by design (factor analysis, cross-validated classifiers)
and return the same :class:`AnalysisResult` shape so the CLI and GUI
can render them uniformly.

All operations are local-only. Where stochastic (K-fold splits, k-means
init) a fixed ``random_state`` is used so results are reproducible for
a given dataset.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from zyuka.analysis.tests import AnalysisResult

MIN_PCA_ROWS = 30
MIN_VIF_ROWS = 20
MIN_HETERO_ROWS = 20
MIN_CLASSIFIER_ROWS = 30
MIN_PROFILE_ROWS = 20


# ---------------------------------------------------------------------------
# Principal component analysis
# ---------------------------------------------------------------------------


def principal_components(
    df: pd.DataFrame,
    columns: Sequence[str],
    n_components: int | None = None,
    variance_target: float = 0.9,
) -> AnalysisResult:
    """Fit PCA on ``columns``; report components reaching ``variance_target``.

    Rows with any missing value across the chosen columns are dropped
    before scaling. Loadings are returned in original-column space.
    """

    cols = list(columns)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(
        name="Principal Component Analysis", kind="dimensionality", columns=cols
    )
    result.n = len(numeric)
    if result.n < MIN_PCA_ROWS or len(cols) < 2:
        result.summary = f"Need ≥ {MIN_PCA_ROWS} complete rows and ≥ 2 columns."
        return result

    scaler = StandardScaler()
    scaled = scaler.fit_transform(numeric.to_numpy())
    max_components = min(len(cols), result.n)
    k = n_components or max_components
    pca = PCA(n_components=k, random_state=42)
    pca.fit(scaled)

    cum = np.cumsum(pca.explained_variance_ratio_)
    keep = (
        int(np.searchsorted(cum, variance_target) + 1) if cum[-1] >= variance_target else len(cum)
    )
    result.metrics = {
        "components_fit": float(k),
        "variance_90pct_components": float(keep),
        "total_variance_explained": float(cum[-1]),
    }
    result.details["explained_variance_ratio"] = pca.explained_variance_ratio_.tolist()
    result.details["cumulative_variance"] = cum.tolist()
    result.details["loadings"] = pd.DataFrame(
        pca.components_.T, index=cols, columns=[f"PC{i + 1}" for i in range(k)]
    ).to_dict()
    result.summary = (
        f"{keep} principal components explain ≥ {variance_target * 100:.0f}% of variance "
        f"across {len(cols)} features (n={result.n})."
    )
    return result


# ---------------------------------------------------------------------------
# Regression diagnostics — VIF, heteroskedasticity
# ---------------------------------------------------------------------------


def variance_inflation_factors(df: pd.DataFrame, columns: Sequence[str]) -> AnalysisResult:
    """VIF per predictor — flag collinearity > 10."""

    from statsmodels.stats.outliers_influence import variance_inflation_factor

    cols = list(columns)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(name="Variance Inflation Factors", kind="diagnostic", columns=cols)
    result.n = len(numeric)
    if result.n < MIN_VIF_ROWS or len(cols) < 2:
        result.summary = f"Need ≥ {MIN_VIF_ROWS} complete rows and ≥ 2 predictors."
        return result
    matrix = numeric.to_numpy(dtype=float)
    vifs: list[dict[str, Any]] = []
    for i, col in enumerate(cols):
        try:
            value = float(variance_inflation_factor(matrix, i))
        except (ValueError, ZeroDivisionError):
            value = float("inf")
        vifs.append({"variable": col, "vif": value})
    high = [v for v in vifs if v["vif"] > 10]
    result.details["vifs"] = vifs
    result.metrics = {"max_vif": max(v["vif"] for v in vifs) if vifs else 0.0}
    result.summary = (
        f"{len(high)} predictor(s) with VIF > 10 "
        f"(max={result.metrics['max_vif']:.2f}; rule of thumb: > 10 indicates collinearity)."
    )
    return result


def breusch_pagan_heteroskedasticity(
    df: pd.DataFrame, outcome: str, predictors: Sequence[str]
) -> AnalysisResult:
    """Breusch-Pagan test for heteroskedasticity on an OLS fit."""

    import statsmodels.api as sm
    from statsmodels.stats.diagnostic import het_breuschpagan

    cols = [outcome, *predictors]
    frame = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(name="Breusch-Pagan", kind="diagnostic", columns=cols)
    result.n = len(frame)
    if result.n < MIN_HETERO_ROWS:
        result.summary = f"Need ≥ {MIN_HETERO_ROWS} complete rows."
        return result
    x = sm.add_constant(frame[list(predictors)].astype(float), has_constant="add")
    y = frame[outcome].astype(float).to_numpy()
    model = sm.OLS(y, x).fit()
    lm, lm_p, f, f_p = het_breuschpagan(model.resid, x)
    result.metrics = {
        "LM_statistic": float(lm),
        "LM_p_value": float(lm_p),
        "F_statistic": float(f),
        "F_p_value": float(f_p),
    }
    verdict = "Heteroskedasticity detected" if lm_p < 0.05 else "Homoskedastic (constant variance)"
    result.summary = f"{verdict} — LM p={lm_p:.4f}, F p={f_p:.4f}."
    return result


# ---------------------------------------------------------------------------
# Classification with cross-validation
# ---------------------------------------------------------------------------


def classify_with_cv(
    df: pd.DataFrame,
    outcome: str,
    predictors: Sequence[str],
    cv: int = 5,
) -> AnalysisResult:
    """Logistic regression + random-forest classifier with K-fold CV.

    Returns accuracy and (for binary outcomes) ROC AUC. Encodes
    categorical predictors via pandas ``get_dummies``.
    """

    cols = [outcome, *predictors]
    frame = df[cols].dropna()
    result = AnalysisResult(name="Classification (CV)", kind="classification", columns=cols)
    result.n = len(frame)
    if result.n < MIN_CLASSIFIER_ROWS:
        result.summary = f"Need ≥ {MIN_CLASSIFIER_ROWS} complete rows."
        return result
    y_raw = frame[outcome]
    classes = sorted(y_raw.dropna().unique().tolist())
    if len(classes) < 2:
        result.summary = f"Outcome {outcome!r} must have ≥ 2 classes."
        return result
    class_to_int = {c: i for i, c in enumerate(classes)}
    y = y_raw.map(class_to_int).to_numpy()
    x = pd.get_dummies(frame[list(predictors)], drop_first=True).astype(float)
    if x.empty:
        result.summary = "No usable predictors after encoding."
        return result

    scoring = "roc_auc" if len(classes) == 2 else "accuracy"
    models: dict[str, Any] = {
        "logistic_regression": LogisticRegression(max_iter=500, random_state=42),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1),
    }
    scores: dict[str, dict[str, float]] = {}
    for name, model in models.items():
        try:
            cv_scores = cross_val_score(model, x.to_numpy(), y, cv=cv, scoring=scoring)
        except ValueError as exc:
            result.warnings.append(f"{name}: {exc}")
            continue
        scores[name] = {
            "mean": float(np.mean(cv_scores)),
            "std": float(np.std(cv_scores)),
        }
    if not scores:
        result.summary = "No model could be fit."
        return result
    result.details["classes"] = [str(c) for c in classes]
    result.details["scoring"] = scoring
    result.details["scores"] = scores
    best_name, best = max(scores.items(), key=lambda kv: kv[1]["mean"])
    result.metrics = {
        "best_mean_score": best["mean"],
        "best_std_score": best["std"],
    }
    result.summary = (
        f"Best model: {best_name} — {scoring}={best['mean']:.3f} "
        f"(±{best['std']:.3f}) over {cv}-fold CV."
    )
    return result


# ---------------------------------------------------------------------------
# Cluster profiling
# ---------------------------------------------------------------------------


def profile_clusters(
    df: pd.DataFrame,
    columns: Sequence[str],
    k: int = 3,
    random_state: int = 42,
) -> AnalysisResult:
    """Fit K-means and describe each cluster by feature means + size."""

    cols = list(columns)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    result = AnalysisResult(name="Cluster profiling", kind="segmentation", columns=cols)
    result.n = len(numeric)
    if result.n < MIN_PROFILE_ROWS or len(cols) < 2:
        result.summary = f"Need ≥ {MIN_PROFILE_ROWS} complete rows and ≥ 2 columns."
        return result
    k = max(2, min(k, result.n // 5))
    scaler = StandardScaler()
    scaled = scaler.fit_transform(numeric.to_numpy())
    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    labels = model.fit_predict(scaled)
    assigned = numeric.copy()
    assigned["__cluster"] = labels
    centroids = assigned.groupby("__cluster").mean().reset_index()
    sizes = assigned["__cluster"].value_counts().sort_index()

    centroids_dicts = centroids.to_dict(orient="records")
    for row in centroids_dicts:
        cid = int(row["__cluster"])
        row["size"] = int(sizes.get(cid, 0))
    result.details["clusters"] = centroids_dicts
    result.metrics = {"k": float(k), "inertia": float(model.inertia_)}
    result.summary = f"{k} clusters profiled on {len(cols)} features (n={result.n})."
    return result
