"""Missingness summary per column and per enumerator."""

from __future__ import annotations

import pandas as pd


def missing_per_column(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    if total == 0:
        return pd.DataFrame(columns=["column", "missing", "pct"])
    rows: list[dict[str, object]] = []
    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum() + (series.astype(str).str.strip() == "").sum())
        # Avoid double-counting pure NaNs that also happen to stringify to "nan".
        missing = min(missing, total)
        rows.append(
            {
                "column": col,
                "missing": missing,
                "pct": round(100.0 * missing / total, 2),
            }
        )
    return pd.DataFrame(rows).sort_values("pct", ascending=False).reset_index(drop=True)


def missing_per_enumerator(df: pd.DataFrame, enumerator_col: str = "enumerator_id") -> pd.DataFrame:
    if enumerator_col not in df.columns or df.empty:
        return pd.DataFrame(columns=[enumerator_col, "rows", "missing_cells", "pct"])
    out: list[dict[str, object]] = []
    for enum, group in df.groupby(enumerator_col, dropna=False):
        total_cells = group.size
        missing = int(group.isna().sum().sum())
        out.append(
            {
                enumerator_col: str(enum),
                "rows": len(group),
                "missing_cells": missing,
                "pct": round(100.0 * missing / max(total_cells, 1), 2),
            }
        )
    return pd.DataFrame(out).sort_values("pct", ascending=False).reset_index(drop=True)
