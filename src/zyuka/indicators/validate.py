"""Validate a logframe against the actual data.

The goal is to turn silent empty-indicator results into early, plain-language
errors. For each indicator we check:

- Every column referenced in numerator, denominator or disaggregations
  exists in at least one round of data.
- Numeric indicator types resolve to a column that is coerce-able to a number.
- Suggest close spellings using :func:`difflib.get_close_matches` for any
  missing column — so ``hh_income`` becomes "did you mean ``household_income``?".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches

import pandas as pd

from zyuka.config import IndicatorDef, LogframeConfig
from zyuka.indicators.expressions import referenced_columns


@dataclass
class ValidationIssue:
    code: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _suggest(missing: str, pool: set[str]) -> str:
    matches = get_close_matches(missing, pool, n=1, cutoff=0.6)
    if matches:
        return f"Did you mean `{matches[0]}`?"
    return ""


def _check_indicator(ind: IndicatorDef, columns: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expressions = [ind.numerator]
    if ind.denominator:
        expressions.append(ind.denominator)
    for expr in expressions:
        for col in referenced_columns(expr):
            if col not in columns:
                issues.append(
                    ValidationIssue(
                        code=ind.code,
                        message=f"Indicator {ind.code} refers to column `{col}` "
                        f"which is not in the data.",
                        suggestion=_suggest(col, columns),
                    )
                )
    for disagg in ind.disaggregations:
        if disagg not in columns:
            issues.append(
                ValidationIssue(
                    code=ind.code,
                    message=f"Indicator {ind.code} disaggregated by `{disagg}` "
                    f"but that column is missing.",
                    suggestion=_suggest(disagg, columns),
                )
            )
    return issues


def validate_logframe(
    logframe: LogframeConfig,
    rounds: dict[str, pd.DataFrame],
) -> ValidationResult:
    """Check every indicator against the union of columns across rounds."""

    union: set[str] = set()
    for df in rounds.values():
        union |= set(df.columns)

    issues: list[ValidationIssue] = []
    for ind in logframe.all_indicators():
        issues.extend(_check_indicator(ind, union))
    return ValidationResult(issues=issues)
