"""Enumerator performance summary.

Columns in the output:

- ``enumerator_id``
- ``submissions``
- ``avg_duration_minutes``
- ``flag_rate`` — share of this enumerator's submissions that are flagged.
"""

from __future__ import annotations

import pandas as pd


def enumerator_summary(
    df: pd.DataFrame,
    flagged_row_ids: set[int] | None = None,
    enumerator_col: str = "enumerator_id",
    start_col: str = "start",
    end_col: str = "end",
) -> pd.DataFrame:
    if enumerator_col not in df.columns or df.empty:
        return pd.DataFrame(
            columns=[enumerator_col, "submissions", "avg_duration_minutes", "flag_rate"]
        )

    flags = flagged_row_ids or set()
    rows: list[dict[str, object]] = []
    for enum, group in df.groupby(enumerator_col, dropna=False):
        if start_col in group.columns and end_col in group.columns:
            start = pd.to_datetime(group[start_col], errors="coerce")
            end = pd.to_datetime(group[end_col], errors="coerce")
            duration = (end - start).dt.total_seconds() / 60.0
            avg = round(float(duration.mean(skipna=True)), 2) if duration.notna().any() else None
        else:
            avg = None
        flagged = sum(int(idx in flags) for idx in group.index)
        rows.append(
            {
                enumerator_col: str(enum),
                "submissions": len(group),
                "avg_duration_minutes": avg,
                "flag_rate": round(flagged / len(group), 3) if len(group) else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("submissions", ascending=False).reset_index(drop=True)
