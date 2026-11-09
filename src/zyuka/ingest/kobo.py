"""Readers for KoboToolbox CSV / XLSX exports.

Kobo exports group-form questions as ``group_x/question``. This module strips
those prefixes by default but keeps the raw mapping so callers can still look
up the fully-qualified name if they need to. ``select_multiple`` columns can be
exported two ways (space-separated single column, or one-hot columns);
:func:`normalise_select_multiple` detects both.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from zyuka.errors import IngestError


def read_kobo_csv(path: Path) -> pd.DataFrame:
    """Read a Kobo CSV export into a DataFrame.

    Kobo defaults to UTF-8 and ``,`` as the delimiter but offers ``;``. We try
    the comma first and only fall back to ``;`` when a single-column result
    suggests we picked the wrong separator.
    """

    if not path.exists():
        raise IngestError(f"File not found: {path}", suggest="Check the path and try again.")
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError as exc:
            raise IngestError(
                f"Could not parse {path.name}: {exc}",
                suggest="Open the file and check it is a valid CSV / Kobo export.",
            ) from exc
    else:  # pragma: no cover
        raise IngestError(
            f"Could not decode {path.name}",
            suggest="Convert the file to UTF-8 and try again.",
        )
    # Fall back to ``;`` if the comma read produced a single column that still
    # contains a semicolon — a strong indicator we picked the wrong delimiter.
    if df.shape[1] == 1 and df.columns[0].count(";") >= 1:
        df = pd.read_csv(path, sep=";", encoding=encoding)
    return df


def read_kobo_xlsx(path: Path, sheet: str | int = 0) -> pd.DataFrame:
    """Read a Kobo XLSX export into a DataFrame."""

    if not path.exists():
        raise IngestError(f"File not found: {path}", suggest="Check the path and try again.")
    try:
        return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except Exception as exc:
        raise IngestError(
            f"Could not read XLSX {path.name}: {exc}",
            suggest="Open the file in Excel to check it is not corrupted.",
        ) from exc


def strip_group_prefixes(df: pd.DataFrame) -> pd.DataFrame:
    """Remove ``group/`` prefixes from column names, preserving the suffix.

    Collisions (two groups with the same leaf name) keep the first occurrence
    and append a ``__N`` suffix to the rest so no data is silently dropped.
    """

    new_columns: list[str] = []
    seen: dict[str, int] = {}
    for col in df.columns:
        leaf = str(col).rsplit("/", 1)[-1]
        if leaf not in seen:
            seen[leaf] = 1
            new_columns.append(leaf)
        else:
            seen[leaf] += 1
            new_columns.append(f"{leaf}__{seen[leaf]}")
    out = df.copy()
    out.columns = pd.Index(new_columns)
    return out


def normalise_select_multiple(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Normalise one-hot ``select_multiple`` exports into a single list column.

    Kobo exports ``select_multiple`` fields as either:
      1. A single column with space-separated choice codes, or
      2. One column per choice, with ``0``/``1`` values.

    If ``columns`` is ``None``, this function scans for groups of columns that
    share a common prefix and whose values are strictly in ``{0, 1, "0", "1"}``.
    The returned frame keeps one column per field, holding a space-separated
    string of selected codes (so downstream parsing is identical to case 1).
    """

    out = df.copy()
    if columns:
        groups: list[tuple[str, list[str]]] = [
            (prefix, [c for c in df.columns if str(c).startswith(f"{prefix}/")])
            for prefix in columns
        ]
    else:
        groups = _detect_onehot_groups(df)
    for prefix, children in groups:
        if not children:
            continue
        leaves = [str(c).split("/")[-1] for c in children]
        onehot = out[children].fillna(0).astype(str).replace({"1.0": "1", "0.0": "0"})
        out[prefix] = _collapse_onehot(onehot, leaves)
        out = out.drop(columns=children)
    return out


def _collapse_onehot(onehot: pd.DataFrame, leaves: list[str]) -> pd.Series:
    return onehot.apply(
        lambda row: " ".join(leaf for leaf, v in zip(leaves, row, strict=False) if v == "1"),
        axis=1,
    )


def _detect_onehot_groups(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    """Return ``(prefix, columns)`` groups that look like one-hot exports."""

    groups: dict[str, list[str]] = {}
    for col in df.columns:
        name = str(col)
        if "/" not in name:
            continue
        prefix, _ = name.rsplit("/", 1)
        groups.setdefault(prefix, []).append(name)

    result: list[tuple[str, list[str]]] = []
    for prefix, cols in groups.items():
        if len(cols) < 2:
            continue
        stacked = pd.concat([df[c] for c in cols], ignore_index=True)
        values = stacked.dropna().astype(str).unique()
        if set(values).issubset({"0", "1", "0.0", "1.0"}):
            result.append((prefix, cols))
    return result
