"""Indicator engine — compute a single indicator value against a DataFrame.

Each indicator in the logframe has a ``type`` from
:data:`linga.config.IndicatorType` and a ``numerator`` filter expression. The
engine applies the filter row-by-row and then reduces according to type:

- ``count`` — rows passing the filter.
- ``count_unique`` — distinct non-null values in the numerator column.
- ``proportion`` — count(numerator) / count(denominator), expressed 0.0-1.0.
- ``mean`` / ``median`` / ``sum`` — numeric reduction on the numerator column.
- ``ratio`` — same as proportion but allowed to exceed 1.0.

A missing column produces ``None`` rather than raising; the validator surfaces
schema mismatches up front.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from linga.config import IndicatorDef, IndicatorType
from linga.errors import IndicatorError
from linga.indicators.expressions import evaluate, referenced_columns


@dataclass(frozen=True)
class IndicatorValue:
    code: str
    type: IndicatorType
    value: float | int | None
    numerator: int | None
    denominator: int | None
    note: str = ""


def _row_mask(df: pd.DataFrame, expression: str) -> pd.Series:
    """Return a boolean Series marking rows that match ``expression``."""

    if not expression or expression.strip() in {"*", "all", "1", "True"}:
        return pd.Series([True] * len(df), index=df.index)

    missing = referenced_columns(expression) - set(df.columns)
    if missing:
        raise IndicatorError(
            f"Expression references missing columns: {sorted(missing)}",
            suggest="Check column names in the logframe match the data exactly.",
        )

    records = df.to_dict(orient="records")
    out = [evaluate(expression, {str(k): v for k, v in row.items()}) for row in records]
    return pd.Series(out, index=df.index)


def _numeric_series(df: pd.DataFrame, expression: str) -> pd.Series:
    """Pick the first referenced column and return it as a numeric Series.

    For ``mean`` / ``median`` / ``sum`` the author points the expression at a
    single numeric column (``income``) and optionally adds filters. If more
    than one column is referenced we use the first one in alphabetical order
    so the choice is stable.
    """

    cols = sorted(referenced_columns(expression))
    if not cols:
        raise IndicatorError(
            f"Numeric indicator needs a column reference: {expression!r}",
            suggest="Add the numeric column name to the expression.",
        )
    col = cols[0]
    if col not in df.columns:
        raise IndicatorError(f"Column not in data: {col!r}")
    return pd.to_numeric(df[col], errors="coerce")


def compute_indicator(df: pd.DataFrame, indicator: IndicatorDef) -> IndicatorValue:
    """Compute a single indicator against a round-level DataFrame."""

    if df.empty:
        return IndicatorValue(indicator.code, indicator.type, None, 0, 0, note="empty dataset")

    numerator_mask = _row_mask(df, indicator.numerator)
    numerator_n = int(numerator_mask.sum())

    if indicator.type == "count":
        return IndicatorValue(indicator.code, indicator.type, numerator_n, numerator_n, None)

    if indicator.type == "count_unique":
        cols = sorted(referenced_columns(indicator.numerator))
        if not cols or cols[0] not in df.columns:
            raise IndicatorError(f"count_unique needs a column reference: {indicator.numerator!r}")
        filtered = df.loc[numerator_mask, cols[0]].dropna()
        value = int(filtered.nunique())
        return IndicatorValue(indicator.code, indicator.type, value, value, None)

    if indicator.type in {"proportion", "ratio"}:
        denom_expr = indicator.denominator or "True"
        denom_mask = _row_mask(df, denom_expr)
        denom_n = int(denom_mask.sum())
        if denom_n == 0:
            return IndicatorValue(
                indicator.code, indicator.type, None, numerator_n, 0, note="denominator is 0"
            )
        ratio = numerator_n / denom_n
        if indicator.type == "proportion" and ratio > 1.0:
            # Numerator must be a subset of the denominator for a true
            # proportion; surface this to the author instead of returning >1.
            return IndicatorValue(
                indicator.code,
                indicator.type,
                ratio,
                numerator_n,
                denom_n,
                note="numerator exceeds denominator",
            )
        return IndicatorValue(indicator.code, indicator.type, ratio, numerator_n, denom_n)

    if indicator.type in {"mean", "median", "sum"}:
        values = _numeric_series(df, indicator.numerator).loc[numerator_mask].dropna()
        if values.empty:
            return IndicatorValue(
                indicator.code, indicator.type, None, 0, None, note="no numeric values"
            )
        if indicator.type == "mean":
            result = float(values.mean())
        elif indicator.type == "median":
            result = float(values.median())
        else:
            result = float(values.sum())
        if math.isnan(result):
            return IndicatorValue(indicator.code, indicator.type, None, 0, None)
        n = len(values)
        return IndicatorValue(indicator.code, indicator.type, result, n, n)

    raise IndicatorError(f"Unknown indicator type: {indicator.type!r}")
