"""Evaluate XLSForm constraint / relevant expressions against a DataFrame.

Expressions are translated by :mod:`linga.ingest.xlsform.translate_expression`
and evaluated with :meth:`pandas.DataFrame.query`. We expose a single helper
``linga_selected`` for the ``selected(., 'code')`` idiom. Unsupported
expressions are caught and reported as warnings; they never raise.
"""

from __future__ import annotations

import pandas as pd

from linga.errors import IngestError
from linga.ingest.xlsform import UnsupportedExpression, XLSForm, translate_expression


def _linga_selected(series: pd.Series, code: str) -> pd.Series:
    """Return True where ``series`` (space-separated codes) contains ``code``."""

    return series.astype(str).fillna("").str.split().apply(lambda xs: code in xs)


def find_constraint_violations(df: pd.DataFrame, form: XLSForm) -> pd.DataFrame:
    """Return rows that violate any field's ``constraint`` expression."""

    return _apply(df, form, which="constraint")


def find_relevant_violations(df: pd.DataFrame, form: XLSForm) -> pd.DataFrame:
    """Return rows that answer a field whose ``relevant`` expression is False."""

    return _apply(df, form, which="relevant")


def _apply(df: pd.DataFrame, form: XLSForm, which: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for q in form.questions.values():
        raw = getattr(q, which)
        if not raw or q.name not in df.columns:
            continue
        try:
            translated = translate_expression(raw, current_field=q.name)
        except UnsupportedExpression:
            continue
        try:
            mask = df.eval(translated, local_dict={"linga_selected": _linga_selected})
            if not isinstance(mask, pd.Series):
                continue
            mask = ~mask.astype(bool)
        except (SyntaxError, ValueError, KeyError, IngestError, TypeError):
            continue
        for idx in df.index[mask.fillna(False)]:
            rows.append(
                {
                    "row_index": int(idx),
                    "column": q.name,
                    "reason": f"{which} violation",
                }
            )
    return pd.DataFrame(rows, columns=["row_index", "column", "reason"])
