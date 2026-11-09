"""Multi-round dataset loading.

Each survey round (baseline / midline / endline or custom) is one Kobo / ODK
export. :func:`load_rounds` reads them, tags each row with a ``round`` column
and returns a mapping. :func:`load_round` is the single-file convenience used
by ``zyuka check``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from zyuka.errors import IngestError
from zyuka.ingest.kobo import read_kobo_csv, read_kobo_xlsx, strip_group_prefixes
from zyuka.ingest.odk import read_odk_csv, read_odk_xlsx


@dataclass
class Round:
    name: str
    path: Path
    df: pd.DataFrame


def read_table(path: Path, source: str = "auto") -> pd.DataFrame:
    """Read a single data file (CSV or XLSX) from Kobo or ODK."""

    suffix = path.suffix.lower()
    if source == "odk" or (source == "auto" and "odk" in path.name.lower()):
        reader_csv, reader_xlsx = read_odk_csv, read_odk_xlsx
    else:
        reader_csv, reader_xlsx = read_kobo_csv, read_kobo_xlsx
    if suffix == ".csv":
        df = reader_csv(path)
    elif suffix in {".xlsx", ".xlsm"}:
        df = reader_xlsx(path)
    else:
        raise IngestError(
            f"Unsupported file type: {path.name}",
            suggest="Export the survey as CSV or XLSX.",
        )
    return df


def load_round(path: Path, round_name: str, source: str = "auto") -> pd.DataFrame:
    df = read_table(path, source=source)
    df = strip_group_prefixes(df)
    df["round"] = round_name
    return df


def load_rounds(paths: dict[str, Path], source: str = "auto") -> dict[str, pd.DataFrame]:
    """Load one file per round and return a dict keyed by round name."""

    return {name: load_round(path, name, source=source) for name, path in paths.items()}
