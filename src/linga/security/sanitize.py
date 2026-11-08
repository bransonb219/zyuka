"""Output sanitisation to defeat CSV / Excel formula injection.

Spreadsheet programs treat a cell that begins with ``=``, ``+``, ``-``, ``@``
or a tab as a formula. A respondent typing ``=HYPERLINK("http://...")`` into
an "other, specify" field can therefore run code when an M&E officer opens
the exported CSV. We prepend a single apostrophe to any such cell before
writing; Excel renders the cell exactly as typed but does not evaluate it.

Separately we refuse Excel files that advertise VBA macros (``.xlsm``) and
cap file size on ingest.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from linga.errors import SecurityError

DANGEROUS_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")
DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB
MACRO_EXTENSIONS: frozenset[str] = frozenset({".xlsm", ".xlsb"})


def sanitise_cell(value: object) -> object:
    """Return ``value`` with a leading apostrophe if it starts with a formula char.

    Non-strings are passed through unchanged (numeric cells are not injectable).
    """

    if not isinstance(value, str) or not value:
        return value
    if value.startswith(DANGEROUS_PREFIXES):
        return "'" + value
    return value


def sanitise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with every string cell sanitised in-place."""

    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(sanitise_cell)
    return out


def check_file_size(path: Path, max_bytes: int = DEFAULT_MAX_FILE_BYTES) -> None:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise SecurityError(
            f"File {path.name} is {size:,} bytes, over the {max_bytes:,}-byte limit.",
            suggest="Split the file or raise the limit in linga.yml.",
        )


def check_safe_extension(path: Path) -> None:
    if path.suffix.lower() in MACRO_EXTENSIONS:
        raise SecurityError(
            f"Refusing {path.name}: Excel macro files are not accepted.",
            suggest="Re-export as .xlsx or .csv.",
        )
