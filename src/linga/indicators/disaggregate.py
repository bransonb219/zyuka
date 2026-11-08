"""Disaggregated indicator values.

For each disaggregation column named on an indicator we loop over the
observed values in that column and run the indicator engine on the filtered
subset. The result is a mapping ``{column: {value: IndicatorValue}}`` so the
report writer can lay it out as a table per disaggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from linga.config import IndicatorDef
from linga.indicators.engine import IndicatorValue, compute_indicator


@dataclass
class DisaggregatedResult:
    overall: IndicatorValue
    by_column: dict[str, dict[str, IndicatorValue]] = field(default_factory=dict)


def disaggregate_indicator(df: pd.DataFrame, indicator: IndicatorDef) -> DisaggregatedResult:
    """Compute the overall indicator plus one slice per disaggregation column."""

    overall = compute_indicator(df, indicator)
    by_column: dict[str, dict[str, IndicatorValue]] = {}

    for disagg_col in indicator.disaggregations:
        if disagg_col not in df.columns:
            continue
        per_value: dict[str, IndicatorValue] = {}
        values = df[disagg_col].dropna().unique()
        for value in sorted(map(str, values)):
            subset = df[df[disagg_col].astype(str) == value]
            per_value[value] = compute_indicator(subset, indicator)
        by_column[disagg_col] = per_value

    return DisaggregatedResult(overall=overall, by_column=by_column)
