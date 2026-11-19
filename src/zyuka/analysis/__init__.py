"""Exploratory data analysis, analysis-advisor and statistical tests.

This package layers three capabilities on top of a cleaned dataset:

* :mod:`zyuka.analysis.eda` — profile a DataFrame (dtypes, missingness,
  cardinality, shape of numeric columns, top categorical values, pairwise
  numeric correlation).
* :mod:`zyuka.analysis.advisor` — a rule-based recommender that reads the
  profile and proposes which statistical tests make sense given column
  types, sample size and distribution.
* :mod:`zyuka.analysis.tests` — thin, deterministic wrappers around scipy /
  statsmodels / scikit-learn so every test returns a plain dataclass the
  CLI and GUI can render without re-interpreting raw library output.

Everything runs locally; no remote calls, no telemetry. PII columns
flagged by :mod:`zyuka.privacy.scanner` are expected to be excluded by
callers before analysis.
"""

from __future__ import annotations

from zyuka.analysis.advisor import AnalysisSuggestion, suggest_analyses
from zyuka.analysis.eda import ColumnProfile, DatasetProfile, profile_dataframe
from zyuka.analysis.modelling import (
    breusch_pagan_heteroskedasticity,
    classify_with_cv,
    principal_components,
    profile_clusters,
    variance_inflation_factors,
)
from zyuka.analysis.qualitative import (
    SentimentReport,
    Theme,
    analyse_sentiment,
    build_codebook,
    cluster_responses,
    extract_themes,
    sentiment_result,
)
from zyuka.analysis.tests import (
    AnalysisResult,
    cronbach_alpha,
    kmeans_cluster,
    kruskal_wallis,
    mann_whitney_u,
    normality_test,
    oneway_anova,
    ordinary_least_squares,
    pairwise_correlations,
    pearson_correlation,
    sample_covariance,
    spearman_correlation,
    t_test_independent,
    two_way_chi_square,
)

__all__ = [
    "AnalysisResult",
    "AnalysisSuggestion",
    "ColumnProfile",
    "DatasetProfile",
    "SentimentReport",
    "Theme",
    "analyse_sentiment",
    "breusch_pagan_heteroskedasticity",
    "build_codebook",
    "classify_with_cv",
    "cluster_responses",
    "cronbach_alpha",
    "extract_themes",
    "kmeans_cluster",
    "kruskal_wallis",
    "mann_whitney_u",
    "normality_test",
    "oneway_anova",
    "ordinary_least_squares",
    "pairwise_correlations",
    "pearson_correlation",
    "principal_components",
    "profile_clusters",
    "profile_dataframe",
    "sample_covariance",
    "sentiment_result",
    "spearman_correlation",
    "suggest_analyses",
    "t_test_independent",
    "two_way_chi_square",
    "variance_inflation_factors",
]
