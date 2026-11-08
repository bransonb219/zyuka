"""Masking helpers for GUI previews.

Every value shown in the Streamlit app passes through one of these so raw
PII never reaches the browser. The heuristics mirror the PII scanner's
column-name signals: anything likely to contain identifiers is masked by
default.
"""

from __future__ import annotations

import pandas as pd

RISKY_COLUMN_HINTS: tuple[str, ...] = (
    "name",
    "nrc",
    "phone",
    "email",
    "address",
    "gps",
    "lat",
    "lon",
    "dob",
    "birth",
    "notes",
    "comment",
    "other_specify",
    "pid",
    "respondent",
)


def _mask_value(value: object) -> str:
    """Return a stable, short masked representation of ``value``."""

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    # Show the first and last character only.
    return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"


def _is_risky(column: str) -> bool:
    lower = column.lower()
    return any(hint in lower for hint in RISKY_COLUMN_HINTS)


def masked_preview(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return the first ``limit`` rows with risky columns masked."""

    preview = df.head(limit).copy()
    for col in preview.columns:
        if _is_risky(col):
            preview[col] = preview[col].map(_mask_value)
    return preview
