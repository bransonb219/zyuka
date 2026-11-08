"""Interview-duration checks.

Flag interviews shorter than a configurable minimum (default 2 min) and ones
that cross midnight (``end`` before ``start`` when the local date differs).
"""

from __future__ import annotations

import pandas as pd


def find_duration_issues(
    df: pd.DataFrame,
    start_col: str = "start",
    end_col: str = "end",
    min_minutes: float = 2.0,
) -> pd.DataFrame:
    if start_col not in df.columns or end_col not in df.columns:
        return pd.DataFrame(columns=["row_index", "column", "reason"])
    start = pd.to_datetime(df[start_col], errors="coerce")
    end = pd.to_datetime(df[end_col], errors="coerce")
    duration = (end - start).dt.total_seconds() / 60.0

    short = (duration < min_minutes) & duration.notna()
    overnight = (end.dt.date != start.dt.date) & end.notna() & start.notna()

    rows: list[dict[str, object]] = []
    for idx in df.index[short]:
        rows.append({"row_index": int(idx), "column": end_col, "reason": "interview too short"})
    for idx in df.index[overnight]:
        rows.append({"row_index": int(idx), "column": end_col, "reason": "interview overnight"})
    return pd.DataFrame(rows, columns=["row_index", "column", "reason"])
