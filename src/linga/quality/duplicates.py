"""Duplicate-submission detection.

Two strategies:

1. Exact match on ``_uuid`` / ``instanceID`` — these should always be unique.
2. "Fuzzy" match on ``(pseudonymised_id_candidate, submission_date)``. For
   the quality step we don't yet have a key, so we fall back to a stable
   hash of the raw identifier(s) the caller nominates.
"""

from __future__ import annotations

import hashlib

import pandas as pd


def duplicate_uuids(df: pd.DataFrame) -> pd.DataFrame:
    """Return the rows whose ``_uuid`` / ``instanceID`` is not unique."""

    for col in ("_uuid", "instanceID"):
        if col in df.columns:
            mask = df[col].notna() & df.duplicated(subset=[col], keep=False)
            if mask.any():
                return df.loc[mask, [col]].assign(reason=f"duplicate {col}")
    return pd.DataFrame(columns=["reason"])


def duplicate_identity(
    df: pd.DataFrame, id_cols: list[str], date_col: str | None = None
) -> pd.DataFrame:
    """Return rows that share the same (hashed id, date)."""

    if not id_cols or not all(c in df.columns for c in id_cols):
        return pd.DataFrame(columns=["reason"])
    hashed = df[id_cols].astype(str).agg("|".join, axis=1).map(_sha)
    keys = pd.DataFrame({"__hash": hashed})
    if date_col and date_col in df.columns:
        keys["__date"] = pd.to_datetime(df[date_col], errors="coerce").dt.date.astype(str)
        subset = ["__hash", "__date"]
    else:
        subset = ["__hash"]
    mask = keys.duplicated(subset=subset, keep=False) & keys["__hash"].notna()
    if not mask.any():
        return pd.DataFrame(columns=["reason"])
    out = df.loc[mask].copy()
    out["reason"] = "duplicate identity"
    return out[["reason"]]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
