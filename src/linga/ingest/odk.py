"""Readers for ODK exports.

ODK Central and ODK Collect produce CSVs in a shape very similar to Kobo's,
so this module largely wraps the Kobo readers and renames the standard
``instanceID`` column to the same ``_uuid`` used by Kobo so downstream code
can treat both sources uniformly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from linga.ingest.kobo import read_kobo_csv, read_kobo_xlsx


def read_odk_csv(path: Path) -> pd.DataFrame:
    df = read_kobo_csv(path)
    return _normalise_uuid(df)


def read_odk_xlsx(path: Path, sheet: str | int = 0) -> pd.DataFrame:
    df = read_kobo_xlsx(path, sheet=sheet)
    return _normalise_uuid(df)


def _normalise_uuid(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a ``_uuid`` column exists, synthesising it from ``instanceID``."""

    out = df.copy()
    if "_uuid" not in out.columns and "instanceID" in out.columns:
        out["_uuid"] = out["instanceID"].astype(str).str.replace("uuid:", "", regex=False)
    return out
