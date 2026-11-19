"""Rule-based analysis advisor.

Reads a :class:`~zyuka.analysis.eda.DatasetProfile` and emits a list of
:class:`AnalysisSuggestion` entries ranked by confidence. The rules are
intentionally conservative — a suggestion appears only when its sample
size and column types pass a hard gate. The goal is "the user sees the
right test for *their* data" rather than every possible test.

Each suggestion has an ``explanation`` field explaining *why* the
advisor picked it — the GUI shows that string verbatim so researchers
can audit the suggestion before running the test.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from zyuka.analysis.eda import ColumnProfile, DatasetProfile, profile_dataframe

# Hard gates (see also zyuka.analysis.tests)
MIN_N = 20
MIN_PER_GROUP = 5
MIN_UNIQUE_CATEGORIES = 2
MAX_CATEGORIES_FOR_GROUP = 10
HIGH_SKEW = 1.0
CRONBACH_MIN_ITEMS = 3
CRONBACH_MAX_ITEMS = 30
LIKERT_MAX_UNIQUE = 11


@dataclass
class AnalysisSuggestion:
    """A single test recommendation produced by the advisor."""

    test: str  # key understood by zyuka.analysis.tests.run_many
    name: str  # display name for the UI
    columns: list[str] = field(default_factory=list)
    rationale: str = ""
    explanation: str = ""
    confidence: float = 0.5  # 0..1 — used only for sort order
    category: str = ""  # high-level grouping for the UI

    def to_dict(self) -> dict[str, object]:
        return {
            "test": self.test,
            "name": self.name,
            "columns": self.columns,
            "rationale": self.rationale,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "category": self.category,
        }


def _is_likely_binary_group(c: ColumnProfile) -> bool:
    return c.kind == "categorical" and 2 <= c.unique <= 2


def _is_likely_multi_group(c: ColumnProfile) -> bool:
    return c.kind == "categorical" and 3 <= c.unique <= MAX_CATEGORIES_FOR_GROUP


def _is_likert(c: ColumnProfile) -> bool:
    """Numeric columns with small discrete range look Likert-like."""

    if c.kind != "numeric":
        return False
    if c.unique > LIKERT_MAX_UNIQUE:
        return False
    if c.min is None or c.max is None:
        return False
    span = c.max - c.min
    return 2 <= span <= 10


def suggest_analyses(
    df: pd.DataFrame,
    profile: DatasetProfile | None = None,
    pii_columns: Sequence[str] | None = None,
) -> list[AnalysisSuggestion]:
    """Produce ordered suggestions based on the dataset profile.

    Columns in ``pii_columns`` are excluded from all suggestions so the
    advisor never nudges a user into running stats on raw PII.
    """

    profile = profile or profile_dataframe(df)
    exclude = set(pii_columns or [])
    numeric_cols = [c for c in profile.by_kind("numeric") if c.name not in exclude]
    cat_cols = [c for c in profile.by_kind("categorical") if c.name not in exclude]

    out: list[AnalysisSuggestion] = []
    if profile.n_rows < MIN_N:
        return out

    out.extend(_normality_suggestions(numeric_cols))
    out.extend(_correlation_suggestions(df, numeric_cols))
    out.extend(_reliability_suggestions(numeric_cols))
    out.extend(_group_difference_suggestions(df, numeric_cols, cat_cols))
    out.extend(_association_suggestions(df, cat_cols))
    out.extend(_regression_suggestions(numeric_cols))
    out.extend(_clustering_suggestions(numeric_cols))
    out.extend(_dimensionality_suggestions(numeric_cols))
    out.extend(_classification_suggestions(numeric_cols, cat_cols, df))

    out.sort(key=lambda s: s.confidence, reverse=True)
    return out


def _normality_suggestions(numeric: Sequence[ColumnProfile]) -> list[AnalysisSuggestion]:
    out: list[AnalysisSuggestion] = []
    for col in numeric:
        if col.n - col.missing < MIN_N:
            continue
        skew = abs(col.skew or 0.0)
        confidence = 0.9 if skew > HIGH_SKEW else 0.6
        out.append(
            AnalysisSuggestion(
                test="normality",
                name=f"Normality — {col.name}",
                columns=[col.name],
                category="Distribution",
                rationale=f"Numeric column with skew={col.skew:.2f} across n={col.n - col.missing}.",
                explanation=(
                    "Run before any parametric test (t-test, ANOVA, Pearson). "
                    "If non-normal, prefer Spearman / Mann-Whitney / Kruskal-Wallis."
                ),
                confidence=confidence,
            )
        )
    return out


def _correlation_suggestions(
    df: pd.DataFrame, numeric: Sequence[ColumnProfile]
) -> list[AnalysisSuggestion]:
    out: list[AnalysisSuggestion] = []
    if len(numeric) < 2:
        return out
    names = [c.name for c in numeric]
    for i, a in enumerate(numeric):
        for b in numeric[i + 1 :]:
            skew = max(abs(a.skew or 0.0), abs(b.skew or 0.0))
            if skew > HIGH_SKEW:
                out.append(
                    AnalysisSuggestion(
                        test="spearman",
                        name=f"Spearman — {a.name} vs {b.name}",
                        columns=[a.name, b.name],
                        category="Relationship",
                        rationale=f"Skew = {skew:.2f} — rank-based correlation is safer.",
                        explanation=(
                            "Spearman's ρ ranks the data, so it isn't sensitive to outliers or "
                            "non-linear monotonic trends."
                        ),
                        confidence=0.75,
                    )
                )
            else:
                out.append(
                    AnalysisSuggestion(
                        test="pearson",
                        name=f"Pearson — {a.name} vs {b.name}",
                        columns=[a.name, b.name],
                        category="Relationship",
                        rationale=f"Two numeric columns, |skew| ≤ {HIGH_SKEW:.1f}.",
                        explanation=(
                            "Pearson's r measures linear association between two numeric "
                            "variables when both are roughly symmetric."
                        ),
                        confidence=0.7,
                    )
                )
    if len(names) >= 3:
        out.append(
            AnalysisSuggestion(
                test="covariance",
                name="Covariance matrix (numeric)",
                columns=names,
                category="Relationship",
                rationale=f"{len(names)} numeric columns available.",
                explanation="Covariance is the raw ingredient for PCA, factor analysis, and VIF.",
                confidence=0.4,
            )
        )
    return out


def _reliability_suggestions(numeric: Sequence[ColumnProfile]) -> list[AnalysisSuggestion]:
    likerts = [c for c in numeric if _is_likert(c)]
    if len(likerts) < CRONBACH_MIN_ITEMS:
        return []
    items = likerts[:CRONBACH_MAX_ITEMS]
    return [
        AnalysisSuggestion(
            test="cronbach_alpha",
            name=f"Cronbach's α — {len(items)} Likert-like items",
            columns=[c.name for c in items],
            category="Reliability",
            rationale="Found numeric columns with small discrete ranges that look like a scale.",
            explanation=(
                "α quantifies internal consistency of a composite scale. "
                "α ≥ 0.7 is the usual publishing threshold."
            ),
            confidence=0.65,
        )
    ]


def _group_difference_suggestions(
    df: pd.DataFrame,
    numeric: Sequence[ColumnProfile],
    categorical: Sequence[ColumnProfile],
) -> list[AnalysisSuggestion]:
    out: list[AnalysisSuggestion] = []
    for num in numeric:
        if num.n - num.missing < MIN_N:
            continue
        for cat in categorical:
            if cat.name == num.name or cat.name not in df.columns:
                continue
            counts = df[cat.name].dropna().value_counts()
            big_groups = counts[counts >= MIN_PER_GROUP]
            if len(big_groups) == 2:
                if abs(num.skew or 0.0) > HIGH_SKEW:
                    out.append(
                        AnalysisSuggestion(
                            test="mann_whitney",
                            name=f"Mann-Whitney U — {num.name} by {cat.name}",
                            columns=[num.name, cat.name],
                            category="Group difference",
                            rationale=f"Two groups ≥ {MIN_PER_GROUP}, outcome skew {num.skew:.2f}.",
                            explanation=(
                                "Non-parametric two-group test — robust when the outcome is "
                                "skewed or has outliers."
                            ),
                            confidence=0.8,
                        )
                    )
                else:
                    out.append(
                        AnalysisSuggestion(
                            test="t_test",
                            name=f"Welch's t-test — {num.name} by {cat.name}",
                            columns=[num.name, cat.name],
                            category="Group difference",
                            rationale=f"Two groups ≥ {MIN_PER_GROUP} on a near-normal outcome.",
                            explanation=(
                                "Welch's t-test compares means across two independent groups "
                                "without assuming equal variance."
                            ),
                            confidence=0.78,
                        )
                    )
            elif 3 <= len(big_groups) <= MAX_CATEGORIES_FOR_GROUP:
                if abs(num.skew or 0.0) > HIGH_SKEW:
                    out.append(
                        AnalysisSuggestion(
                            test="kruskal",
                            name=f"Kruskal-Wallis — {num.name} by {cat.name}",
                            columns=[num.name, cat.name],
                            category="Group difference",
                            rationale=f"{len(big_groups)} groups, outcome skew {num.skew:.2f}.",
                            explanation="Non-parametric ANOVA — compares medians across ≥ 3 groups.",
                            confidence=0.76,
                        )
                    )
                else:
                    out.append(
                        AnalysisSuggestion(
                            test="anova",
                            name=f"One-way ANOVA — {num.name} by {cat.name}",
                            columns=[num.name, cat.name],
                            category="Group difference",
                            rationale=f"{len(big_groups)} groups on a near-normal outcome.",
                            explanation="Compares means across ≥ 3 independent groups.",
                            confidence=0.74,
                        )
                    )
    return out


def _association_suggestions(
    df: pd.DataFrame, categorical: Sequence[ColumnProfile]
) -> list[AnalysisSuggestion]:
    out: list[AnalysisSuggestion] = []
    useful = [
        c for c in categorical if MIN_UNIQUE_CATEGORIES <= c.unique <= MAX_CATEGORIES_FOR_GROUP
    ]
    for i, a in enumerate(useful):
        for b in useful[i + 1 :]:
            if a.name not in df.columns or b.name not in df.columns:
                continue
            table = pd.crosstab(df[a.name], df[b.name])
            if table.shape[0] < 2 or table.shape[1] < 2:
                continue
            if int(table.values.sum()) < MIN_N:
                continue
            out.append(
                AnalysisSuggestion(
                    test="chi_square",
                    name=f"χ² — {a.name} × {b.name}",
                    columns=[a.name, b.name],
                    category="Association",
                    rationale=(
                        f"{table.shape[0]}×{table.shape[1]} table, n={int(table.values.sum())}."
                    ),
                    explanation=(
                        "Tests whether two categorical variables are independent. "
                        "On a 2×2 with small expected cells, falls back to Fisher's exact."
                    ),
                    confidence=0.7,
                )
            )
    return out


def _regression_suggestions(numeric: Sequence[ColumnProfile]) -> list[AnalysisSuggestion]:
    if len(numeric) < 3:
        return []
    out: list[AnalysisSuggestion] = []
    names = [c.name for c in numeric if c.n - c.missing >= MIN_N]
    if len(names) < 3:
        return out
    # Pick the column with widest spread as the default outcome.
    outcome = max(numeric, key=lambda c: c.std or 0.0)
    predictors = [c.name for c in numeric if c.name != outcome.name][:5]
    if len(predictors) < 2:
        return out
    out.append(
        AnalysisSuggestion(
            test="ols",
            name=f"OLS — {outcome.name} ~ {' + '.join(predictors)}",
            columns=[outcome.name, *predictors],
            category="Modelling",
            rationale="Found ≥ 3 numeric columns; largest-variance column is the default outcome.",
            explanation=(
                "Fits a linear model and reports R², adjusted R², F-test and per-predictor "
                "coefficients. Swap the outcome on the Analyze page if the default isn't right."
            ),
            confidence=0.55,
        )
    )
    return out


def _clustering_suggestions(numeric: Sequence[ColumnProfile]) -> list[AnalysisSuggestion]:
    cols = [c.name for c in numeric if c.n - c.missing >= MIN_N]
    if len(cols) < 2:
        return []
    out: list[AnalysisSuggestion] = [
        AnalysisSuggestion(
            test="kmeans",
            name=f"K-means clustering ({len(cols)} features)",
            columns=cols[:8],
            category="Segmentation",
            rationale="Several numeric columns available — worth checking for subgroups.",
            explanation=(
                "Standardises the features then fits K-means for k=2..6 and picks the k with "
                "the best silhouette score. Centroids are reported in original units."
            ),
            confidence=0.45,
        )
    ]
    if len(cols) >= 3:
        out.append(
            AnalysisSuggestion(
                test="cluster_profile",
                name=f"Cluster profiling (k=3, {len(cols)} features)",
                columns=cols[:8],
                category="Segmentation",
                rationale="Companion to K-means: describes each cluster in original units.",
                explanation=(
                    "Fits k=3 and reports per-cluster feature means and cluster sizes so you can "
                    "label each cluster meaningfully (e.g. 'low-income urban youth')."
                ),
                confidence=0.4,
            )
        )
    return out


def _dimensionality_suggestions(
    numeric: Sequence[ColumnProfile],
) -> list[AnalysisSuggestion]:
    cols = [c.name for c in numeric if c.n - c.missing >= MIN_N]
    if len(cols) < 4:
        return []
    return [
        AnalysisSuggestion(
            test="pca",
            name=f"Principal component analysis ({len(cols)} features)",
            columns=cols[:12],
            category="Dimensionality",
            rationale=f"{len(cols)} numeric columns — PCA can reveal latent structure.",
            explanation=(
                "Scales features then fits PCA. Reports how many components reach 90% of "
                "variance, plus loadings so you can interpret each component."
            ),
            confidence=0.5,
        ),
        AnalysisSuggestion(
            test="vif",
            name=f"Variance Inflation Factors ({len(cols)} predictors)",
            columns=cols[:8],
            category="Dimensionality",
            rationale="Check if numeric predictors are collinear before OLS.",
            explanation=(
                "A VIF above 10 means a predictor is well-explained by the others, which inflates "
                "OLS standard errors. Drop or combine such columns before fitting a model."
            ),
            confidence=0.48,
        ),
    ]


def _classification_suggestions(
    numeric: Sequence[ColumnProfile],
    categorical: Sequence[ColumnProfile],
    df: pd.DataFrame,
) -> list[AnalysisSuggestion]:
    binary_cats = [c for c in categorical if 2 <= c.unique <= 2 and c.name in df.columns]
    predictors = [c.name for c in numeric if c.n - c.missing >= MIN_N]
    if not binary_cats or len(predictors) < 2:
        return []
    out: list[AnalysisSuggestion] = []
    for outcome in binary_cats[:3]:
        counts = df[outcome.name].dropna().value_counts()
        minority = int(counts.min()) if not counts.empty else 0
        if minority < 10:
            continue
        out.append(
            AnalysisSuggestion(
                test="classifier",
                name=f"Classifier — predict {outcome.name}",
                columns=[outcome.name, *predictors[:6]],
                category="Modelling",
                rationale=(
                    f"Binary outcome with minority class n={minority} and "
                    f"{len(predictors[:6])} numeric predictors."
                ),
                explanation=(
                    "Fits logistic regression and a random forest with 5-fold CV. "
                    "Reports ROC AUC when the outcome is binary."
                ),
                confidence=0.5,
            )
        )
    return out
