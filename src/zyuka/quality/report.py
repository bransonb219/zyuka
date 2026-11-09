"""Top-level quality report used by ``zyuka check``.

Returns a :class:`QualityReport` with:

- ``summary``  — count per check
- ``flags``    — row-id-only flag frame (no PII)
- ``per_enumerator`` — enumerator performance
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from zyuka.ingest.xlsform import XLSForm
from zyuka.quality.constraints import find_constraint_violations, find_relevant_violations
from zyuka.quality.duplicates import duplicate_identity, duplicate_uuids
from zyuka.quality.duration import find_duration_issues
from zyuka.quality.enumerators import enumerator_summary
from zyuka.quality.missing import missing_per_column, missing_per_enumerator
from zyuka.quality.outliers import find_outliers


@dataclass
class QualityReport:
    summary: dict[str, int] = field(default_factory=dict)
    flags: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    per_column_missing: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    per_enumerator_missing: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    per_enumerator: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


def run_quality(
    df: pd.DataFrame,
    form: XLSForm | None = None,
    id_cols: list[str] | None = None,
    numeric_outlier_cols: list[str] | None = None,
) -> QualityReport:
    frames: list[pd.DataFrame] = []

    dup_uuid = duplicate_uuids(df)
    if not dup_uuid.empty:
        dup_uuid = dup_uuid.assign(row_index=dup_uuid.index.astype(int), column="_uuid")
        frames.append(dup_uuid[["row_index", "column", "reason"]])

    dup_id = duplicate_identity(df, id_cols=id_cols or []) if id_cols else pd.DataFrame()
    if not dup_id.empty:
        dup_id = dup_id.assign(row_index=dup_id.index.astype(int), column="identity")
        frames.append(dup_id[["row_index", "column", "reason"]])

    outliers = find_outliers(df, numeric_columns=numeric_outlier_cols)
    if not outliers.empty:
        frames.append(outliers)

    if form is not None:
        cv = find_constraint_violations(df, form)
        rv = find_relevant_violations(df, form)
        if not cv.empty:
            frames.append(cv)
        if not rv.empty:
            frames.append(rv)

    dur = find_duration_issues(df)
    if not dur.empty:
        frames.append(dur)

    if frames:
        flags = pd.concat(frames, ignore_index=True)
    else:
        flags = pd.DataFrame(columns=["row_index", "column", "reason"])

    summary: dict[str, int] = {}
    for reason, group in flags.groupby("reason"):
        summary[str(reason)] = len(group)
    summary["rows"] = len(df)

    flagged_ids = set(flags["row_index"].astype(int)) if not flags.empty else set()

    return QualityReport(
        summary=summary,
        flags=flags,
        per_column_missing=missing_per_column(df),
        per_enumerator_missing=missing_per_enumerator(df),
        per_enumerator=enumerator_summary(df, flagged_row_ids=flagged_ids),
    )
