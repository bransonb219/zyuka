"""Profile a cleaned DataFrame to power the Advisor and the EDA page.

The profile is deterministic and contains only derived statistics
(counts, moments, top-value frequencies). No raw rows are returned, so
the result is safe to surface in the GUI even before PII protection.

Design notes
------------
* The profile distinguishes four column kinds — ``numeric``,
  ``categorical``, ``datetime`` and ``text`` — because the Advisor's
  rules key off this classification.
* ``top_values`` is clipped to 20 entries and the values are converted
  to strings, so a column that happens to contain PII still produces a
  bounded payload. Callers who want to redact further should drop the
  PII columns before calling :func:`profile_dataframe`.
* Correlations use pairwise complete observations and only include
  numeric columns with at least ``MIN_CORR_N`` finite values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

MIN_CORR_N = 10
MAX_TOP_VALUES = 20
TEXT_MIN_MEAN_LENGTH = 25


@dataclass
class ColumnProfile:
    """Per-column summary stats."""

    name: str
    kind: str
    dtype: str
    n: int
    missing: int
    missing_pct: float
    unique: int
    top_values: list[tuple[str, int]] = field(default_factory=list)
    # Numeric-only fields
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    q1: float | None = None
    median: float | None = None
    q3: float | None = None
    max: float | None = None
    skew: float | None = None
    kurtosis: float | None = None
    zero_pct: float | None = None
    # Text-only fields
    mean_length: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict; omits ``None`` fields to stay compact."""

        base: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "dtype": self.dtype,
            "n": self.n,
            "missing": self.missing,
            "missing_pct": self.missing_pct,
            "unique": self.unique,
            "top_values": self.top_values,
        }
        for key in (
            "mean",
            "std",
            "min",
            "q1",
            "median",
            "q3",
            "max",
            "skew",
            "kurtosis",
            "zero_pct",
            "mean_length",
        ):
            value = getattr(self, key)
            if value is not None:
                base[key] = value
        return base


@dataclass
class DatasetProfile:
    """Dataset-wide stats plus the per-column profiles."""

    n_rows: int
    n_cols: int
    duplicate_rows: int
    columns: list[ColumnProfile] = field(default_factory=list)
    correlations: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["a", "b", "r", "n"])
    )

    def by_kind(self, kind: str) -> list[ColumnProfile]:
        return [c for c in self.columns if c.kind == kind]

    def column(self, name: str) -> ColumnProfile | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "duplicate_rows": self.duplicate_rows,
            "columns": [c.to_dict() for c in self.columns],
            "correlations": self.correlations.to_dict(orient="records"),
        }


def _classify(series: pd.Series) -> str:
    """Bucket a column into ``numeric`` / ``categorical`` / ``datetime`` / ``text``."""

    if is_bool_dtype(series):
        return "categorical"
    if is_datetime64_any_dtype(series):
        return "datetime"
    if is_numeric_dtype(series):
        return "numeric"
    dtype_name = str(series.dtype).lower()
    if dtype_name == "object" or "string" in dtype_name or "str" in dtype_name:
        non_null = series.dropna().astype(str)
        if non_null.empty:
            return "categorical"
        mean_len = float(non_null.str.len().mean())
        if mean_len >= TEXT_MIN_MEAN_LENGTH:
            return "text"
    return "categorical"


def _top_values(series: pd.Series, limit: int = MAX_TOP_VALUES) -> list[tuple[str, int]]:
    non_null = series.dropna()
    if non_null.empty:
        return []
    counts = non_null.astype(str).value_counts().head(limit)
    return [(str(v), int(c)) for v, c in counts.items()]


def _numeric_stats(series: pd.Series) -> dict[str, float | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return dict.fromkeys(
            ("mean", "std", "min", "q1", "median", "q3", "max", "skew", "kurtosis", "zero_pct")
        )
    return {
        "mean": float(numeric.mean()),
        "std": float(numeric.std(ddof=1)) if len(numeric) > 1 else 0.0,
        "min": float(numeric.min()),
        "q1": float(numeric.quantile(0.25)),
        "median": float(numeric.median()),
        "q3": float(numeric.quantile(0.75)),
        "max": float(numeric.max()),
        "skew": float(numeric.skew()) if len(numeric) > 2 else 0.0,  # type: ignore[arg-type]
        "kurtosis": float(numeric.kurtosis()) if len(numeric) > 3 else 0.0,  # type: ignore[arg-type]
        "zero_pct": float((numeric == 0).mean() * 100.0),
    }


def _profile_column(series: pd.Series) -> ColumnProfile:
    kind = _classify(series)
    n = len(series)
    missing = int(series.isna().sum())
    missing_pct = float(missing / n * 100.0) if n else 0.0
    unique = int(series.dropna().nunique())
    profile = ColumnProfile(
        name=str(series.name),
        kind=kind,
        dtype=str(series.dtype),
        n=n,
        missing=missing,
        missing_pct=missing_pct,
        unique=unique,
        top_values=_top_values(series),
    )
    if kind == "numeric":
        for key, value in _numeric_stats(series).items():
            setattr(profile, key, value)
    elif kind == "text":
        non_null = series.dropna().astype(str)
        if not non_null.empty:
            profile.mean_length = float(non_null.str.len().mean())
    return profile


def _correlation_table(df: pd.DataFrame) -> pd.DataFrame:
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return pd.DataFrame(columns=["a", "b", "r", "n"])
    rows: list[dict[str, Any]] = []
    cols = list(numeric_df.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            pair = numeric_df[[a, b]].dropna()
            if len(pair) < MIN_CORR_N:
                continue
            if pair[a].std(ddof=1) == 0 or pair[b].std(ddof=1) == 0:
                continue
            r = float(pair[a].corr(pair[b]))
            if np.isnan(r):
                continue
            rows.append({"a": str(a), "b": str(b), "r": r, "n": len(pair)})
    out = pd.DataFrame(rows, columns=["a", "b", "r", "n"])
    if out.empty:
        return out
    return out.sort_values("r", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def profile_dataframe(df: pd.DataFrame) -> DatasetProfile:
    """Return a :class:`DatasetProfile` describing ``df``.

    The result is deterministic for a given input; it includes no raw
    rows, only derived statistics. Pass a cleaned frame (post
    :func:`zyuka.quality.remediate.apply_decisions`) for the most
    useful advice downstream.
    """

    columns = [_profile_column(df[c]) for c in df.columns]
    dup = int(df.duplicated().sum())
    return DatasetProfile(
        n_rows=len(df),
        n_cols=int(df.shape[1]),
        duplicate_rows=dup,
        columns=columns,
        correlations=_correlation_table(df),
    )
