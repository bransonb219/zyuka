"""Small-cell suppression for aggregate tables.

A row with ``n < threshold`` is replaced with the sentinel ``"<N"`` (default
``"<5"``). Primary suppression alone leaks information: if only one cell in a
row is suppressed, the margin reveals its value. So we also apply *secondary*
suppression, redacting the next smallest cell in each affected row/column.

Inputs and outputs are pandas ``DataFrames`` with a numeric count column.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SUPPRESSED = "<N"


@dataclass(frozen=True)
class SuppressionResult:
    table: pd.DataFrame
    suppressed_cells: int
    threshold: int


def _sentinel(threshold: int) -> str:
    return f"<{threshold}"


def suppress_series(values: pd.Series, threshold: int = 5) -> pd.Series:
    """Replace any numeric value ``< threshold`` and ``> 0`` with the sentinel.

    Zeros stay as zero because a true zero is not disclosive on its own.
    """

    sentinel = _sentinel(threshold)

    def _apply(v: object) -> object:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return v
        if not isinstance(v, int | float):
            return v
        n = float(v)
        if 0 < n < threshold:
            return sentinel
        return int(n) if n.is_integer() else n

    return values.map(_apply)


def suppress_table(
    df: pd.DataFrame,
    count_cols: list[str],
    threshold: int = 5,
    secondary: bool = True,
) -> SuppressionResult:
    """Apply small-cell suppression to each column in ``count_cols``.

    When ``secondary`` is set and a row has exactly one suppressed cell, the
    next-smallest cell in that row is also suppressed so totals can't reveal
    the hidden value.
    """

    if not count_cols:
        return SuppressionResult(df.copy(), 0, threshold)

    sentinel = _sentinel(threshold)
    out = df.copy()
    for col in count_cols:
        if col in out.columns:
            # Cast to object so sentinel strings and numeric cells can coexist.
            out[col] = suppress_series(out[col], threshold=threshold).astype(object)

    suppressed = int((out[count_cols].astype(object) == sentinel).to_numpy().sum())

    if secondary and len(count_cols) >= 2:
        for idx, row in out.iterrows():
            masked = [c for c in count_cols if row[c] == sentinel]
            if len(masked) == 1:
                remaining = [
                    (c, row[c]) for c in count_cols if c != masked[0] and row[c] != sentinel
                ]
                numeric: list[tuple[str, float]] = []
                for c, v in remaining:
                    if isinstance(v, int | float) and not pd.isna(v):
                        numeric.append((c, float(v)))
                if numeric:
                    victim = min(numeric, key=lambda x: x[1])[0]
                    out.at[idx, victim] = sentinel
                    suppressed += 1
    return SuppressionResult(out, suppressed, threshold)
