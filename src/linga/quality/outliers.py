"""Numeric outlier detection using IQR and z-score."""

from __future__ import annotations

import pandas as pd
from pandas.api.types import is_numeric_dtype


def iqr_outliers(series: pd.Series, k: float = 1.5) -> pd.Series:
    """Return a boolean mask: True where ``series`` is an IQR outlier."""

    s = pd.to_numeric(series, errors="coerce")
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    iqr = q3 - q1
    if pd.isna(iqr) or iqr == 0:
        return pd.Series(False, index=series.index)
    lower, upper = q1 - k * iqr, q3 + k * iqr
    return (s < lower) | (s > upper)


def zscore_outliers(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mu = s.mean()
    sigma = s.std(ddof=0)
    if pd.isna(sigma) or sigma == 0:
        return pd.Series(False, index=series.index)
    return (s - mu).abs() / sigma > threshold


def find_outliers(
    df: pd.DataFrame,
    numeric_columns: list[str] | None = None,
    method: str = "iqr",
) -> pd.DataFrame:
    """Return a flags frame: one row per (row_index, column) outlier."""

    cols = numeric_columns or _default_numeric_columns(df)
    fn = iqr_outliers if method == "iqr" else zscore_outliers
    rows: list[dict[str, object]] = []
    for col in cols:
        if col not in df.columns:
            continue
        mask = fn(df[col])
        for idx in df.index[mask]:
            rows.append(
                {
                    "row_index": int(idx),
                    "column": col,
                    "reason": f"outlier ({method})",
                }
            )
    return pd.DataFrame(rows, columns=["row_index", "column", "reason"])


def _default_numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if is_numeric_dtype(df[c])]
