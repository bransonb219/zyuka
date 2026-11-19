"""Remediate detected quality issues with user-approved fixes.

The quality pipeline detects problems; this module *proposes* fixes for
each issue group and applies the ones the user approves. Everything is
deterministic and keyed by (reason, column) so the same approval can be
replayed from :mod:`zyuka.quality.rules`.

Fix kinds
---------
``drop_duplicate_rows``
    Keep the first duplicate per key, scored by row-completeness (fewest
    missing cells wins ties). Covers ``duplicate _uuid`` and
    ``duplicate identity`` flags.
``impute_mode`` / ``impute_median``
    Fill blank cells in a column with the mode (categorical) or median
    (numeric). Chosen as the default based on dtype.
``drop_rows``
    Remove the flagged rows entirely. Used only when the user explicitly
    picks it — never a default — because row loss is destructive.
``winsorize``
    Cap values at the ``p_low`` / ``p_high`` percentiles. Default for
    numeric outliers; preserves row count.
``nullify_cells``
    Blank the flagged cells only. Default for constraint / relevant
    violations: the row stays, the invalid answer disappears.
``flag_only``
    Record the issue in ``outputs/clean/review_{round}.csv`` but leave
    the data alone. Default for soft signals (short / overnight
    interview).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

VALID_KINDS = (
    "drop_duplicate_rows",
    "impute_mode",
    "impute_median",
    "drop_rows",
    "winsorize",
    "nullify_cells",
    "flag_only",
)


@dataclass(frozen=True)
class FixAction:
    """A proposed fix for one group of flags sharing (reason, column)."""

    kind: str
    reason: str
    column: str
    row_indices: tuple[int, ...]
    params: Mapping[str, Any] = field(default_factory=dict)
    rationale: str = ""

    @property
    def group_key(self) -> tuple[str, str]:
        return (self.reason, self.column)


@dataclass
class CleaningDecision:
    """User choice on a :class:`FixAction` — approve / modify / reject."""

    action: FixAction
    status: str  # "approved" | "rejected" | "modified"
    override_kind: str | None = None
    override_params: Mapping[str, Any] | None = None

    @property
    def effective_kind(self) -> str:
        return self.override_kind or self.action.kind

    @property
    def effective_params(self) -> Mapping[str, Any]:
        return self.override_params if self.override_params is not None else self.action.params


@dataclass
class CleaningResult:
    """What :func:`apply_decisions` produced."""

    cleaned: pd.DataFrame
    applied: list[CleaningDecision] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    review_rows: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["row_index", "column", "reason"])
    )


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


def propose_actions(
    df: pd.DataFrame,
    flags: pd.DataFrame,
    per_column_missing: pd.DataFrame | None = None,
    missing_threshold_pct: float = 5.0,
) -> list[FixAction]:
    """Group ``flags`` by (reason, column) and attach a default :class:`FixAction`.

    Also adds imputation proposals for columns whose missingness exceeds
    ``missing_threshold_pct`` (default 5%). Missingness isn't a row-level
    flag so it comes from ``per_column_missing`` instead.
    """

    actions: list[FixAction] = []

    if not flags.empty:
        for (reason, column), group in flags.groupby(["reason", "column"], sort=False):
            rows = tuple(int(i) for i in group["row_index"])
            actions.append(_default_action(df, str(reason), str(column), rows))

    if per_column_missing is not None and not per_column_missing.empty:
        for _, row in per_column_missing.iterrows():
            pct = float(row["pct"])
            if pct < missing_threshold_pct:
                continue
            col = str(row["column"])
            if col not in df.columns:
                continue
            kind = "impute_median" if is_numeric_dtype(df[col]) else "impute_mode"
            missing_rows = tuple(int(i) for i in df.index[df[col].isna()])
            actions.append(
                FixAction(
                    kind=kind,
                    reason="missingness",
                    column=col,
                    row_indices=missing_rows,
                    params={"pct": pct},
                    rationale=(
                        f"{pct:.1f}% of {col!r} is blank. "
                        f"Default: {'median' if kind == 'impute_median' else 'mode'} impute."
                    ),
                )
            )

    return actions


def _default_action(df: pd.DataFrame, reason: str, column: str, rows: tuple[int, ...]) -> FixAction:
    """Pick the default :class:`FixAction` for a flag group."""

    r = reason.lower()
    if r.startswith("duplicate"):
        return FixAction(
            kind="drop_duplicate_rows",
            reason=reason,
            column=column,
            row_indices=rows,
            params={"key_column": column if column in df.columns else "_uuid"},
            rationale="Keep the most complete submission per duplicate key; drop the rest.",
        )
    if r.startswith("outlier"):
        return FixAction(
            kind="winsorize",
            reason=reason,
            column=column,
            row_indices=rows,
            params={"p_low": 0.01, "p_high": 0.99},
            rationale="Cap extreme values at the 1st/99th percentiles. Row count is preserved.",
        )
    if r.endswith("violation"):
        return FixAction(
            kind="nullify_cells",
            reason=reason,
            column=column,
            row_indices=rows,
            params={},
            rationale="Blank the offending answer; the row stays in the dataset.",
        )
    if r.startswith("interview"):
        return FixAction(
            kind="flag_only",
            reason=reason,
            column=column,
            row_indices=rows,
            params={},
            rationale="Soft signal — leave data as-is and record the row in review_*.csv.",
        )
    return FixAction(
        kind="flag_only",
        reason=reason,
        column=column,
        row_indices=rows,
        params={},
        rationale="Unknown flag — recorded for review, no automatic fix.",
    )


# ---------------------------------------------------------------------------
# Fix functions (pure)
# ---------------------------------------------------------------------------


def drop_duplicate_rows(
    df: pd.DataFrame, rows: Iterable[int], key_column: str
) -> tuple[pd.DataFrame, int]:
    """Keep the most-complete row per duplicate key; drop the rest.

    ``rows`` are the flagged row indices (all members of each duplicate
    group). ``key_column`` is the column whose duplication caused the
    flag. Ties on completeness break by index order (keep first).
    """

    rows_set = {int(r) for r in rows if int(r) in df.index}
    if not rows_set or key_column not in df.columns:
        return df.copy(), 0

    subset = df.loc[list(rows_set)].copy()
    subset["__nonnull"] = subset.notna().sum(axis=1)
    subset["__orig_idx"] = subset.index
    subset = subset.sort_values(["__nonnull", "__orig_idx"], ascending=[False, True])
    keep = subset.drop_duplicates(subset=[key_column], keep="first").index
    drop = [i for i in rows_set if i not in set(keep)]
    cleaned = df.drop(index=drop)
    return cleaned, len(drop)


def impute_mode(
    df: pd.DataFrame, column: str, rows: Iterable[int] | None = None
) -> tuple[pd.DataFrame, int]:
    """Fill blanks in ``column`` with the mode. Returns (df, cells filled)."""

    if column not in df.columns:
        return df.copy(), 0
    cleaned = df.copy()
    target = cleaned[column]
    blank = target.isna() | (target.astype(str).str.strip() == "")
    mask = blank.copy()
    if rows is not None:
        rows_set = {int(r) for r in rows}
        mask &= cleaned.index.isin(rows_set)
    if not mask.any():
        return cleaned, 0
    mode = target[~blank].mode()
    if mode.empty:
        return cleaned, 0
    cleaned[column] = target.where(~mask, mode.iloc[0])
    return cleaned, int(mask.sum())


def impute_median(
    df: pd.DataFrame, column: str, rows: Iterable[int] | None = None
) -> tuple[pd.DataFrame, int]:
    """Fill blanks in a numeric ``column`` with the median.

    Upcasts int columns to float when the median is fractional so the
    assignment doesn't lose precision (pandas 4 refuses int-to-float
    overwrites by default).
    """

    if column not in df.columns:
        return df.copy(), 0
    cleaned = df.copy()
    series = pd.to_numeric(cleaned[column], errors="coerce")
    mask = series.isna()
    if rows is not None:
        rows_set = {int(r) for r in rows}
        mask &= cleaned.index.isin(rows_set)
    if not mask.any():
        return cleaned, 0
    median = series[~mask].median()
    if pd.isna(median):
        return cleaned, 0
    cleaned[column] = series.where(~mask, median)
    return cleaned, int(mask.sum())


def drop_rows(df: pd.DataFrame, rows: Iterable[int]) -> tuple[pd.DataFrame, int]:
    """Remove the given rows. Row loss is destructive — use sparingly."""

    rows_list = [int(r) for r in rows if int(r) in df.index]
    if not rows_list:
        return df.copy(), 0
    return df.drop(index=rows_list), len(rows_list)


def winsorize(
    df: pd.DataFrame,
    column: str,
    p_low: float = 0.01,
    p_high: float = 0.99,
) -> tuple[pd.DataFrame, int]:
    """Cap values at ``p_low`` / ``p_high`` percentiles. Row count preserved."""

    if column not in df.columns:
        return df.copy(), 0
    cleaned = df.copy()
    series = pd.to_numeric(cleaned[column], errors="coerce")
    if series.notna().sum() < 2:
        return cleaned, 0
    low, high = float(series.quantile(p_low)), float(series.quantile(p_high))
    affected = ((series < low) | (series > high)) & series.notna()
    cleaned[column] = series.clip(lower=low, upper=high)
    return cleaned, int(affected.sum())


def nullify_cells(df: pd.DataFrame, column: str, rows: Iterable[int]) -> tuple[pd.DataFrame, int]:
    """Blank the (row, column) cells; row survives."""

    if column not in df.columns:
        return df.copy(), 0
    cleaned = df.copy()
    rows_list = [int(r) for r in rows if int(r) in cleaned.index]
    if not rows_list:
        return cleaned, 0
    cleaned.loc[rows_list, column] = pd.NA
    return cleaned, len(rows_list)


# ---------------------------------------------------------------------------
# Apply loop
# ---------------------------------------------------------------------------


def apply_decisions(df: pd.DataFrame, decisions: list[CleaningDecision]) -> CleaningResult:
    """Apply each approved / modified decision in order and return the result."""

    cleaned = df.copy()
    applied: list[CleaningDecision] = []
    summary: dict[str, int] = {}
    review_rows: list[dict[str, Any]] = []

    for decision in decisions:
        if decision.status == "rejected":
            continue
        kind = decision.effective_kind
        params = dict(decision.effective_params)
        action = decision.action
        affected = 0

        if kind == "drop_duplicate_rows":
            cleaned, affected = drop_duplicate_rows(
                cleaned, action.row_indices, params.get("key_column", action.column)
            )
        elif kind == "impute_mode":
            cleaned, affected = impute_mode(cleaned, action.column)
        elif kind == "impute_median":
            cleaned, affected = impute_median(cleaned, action.column)
        elif kind == "drop_rows":
            cleaned, affected = drop_rows(cleaned, action.row_indices)
        elif kind == "winsorize":
            cleaned, affected = winsorize(
                cleaned,
                action.column,
                p_low=float(params.get("p_low", 0.01)),
                p_high=float(params.get("p_high", 0.99)),
            )
        elif kind == "nullify_cells":
            cleaned, affected = nullify_cells(cleaned, action.column, action.row_indices)
        elif kind == "flag_only":
            for idx in action.row_indices:
                review_rows.append(
                    {"row_index": idx, "column": action.column, "reason": action.reason}
                )
            affected = len(action.row_indices)
        else:
            continue

        summary[f"{action.reason} · {action.column}"] = affected
        applied.append(decision)

    review_df = (
        pd.DataFrame(review_rows, columns=["row_index", "column", "reason"])
        if review_rows
        else pd.DataFrame(columns=["row_index", "column", "reason"])
    )
    return CleaningResult(
        cleaned=cleaned.reset_index(drop=True),
        applied=applied,
        summary=summary,
        review_rows=review_df,
    )
