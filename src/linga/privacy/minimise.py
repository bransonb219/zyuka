"""Column minimisation — keep only what the logframe + allowlists need.

Dropping unused columns is the single biggest privacy win: data not held is
data that can't leak. The reduction happens *before* pseudonymisation so we
also don't spend HMAC cycles on columns we'd discard anyway.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def extract_referenced_columns(expressions: Iterable[str]) -> set[str]:
    """Return columns referenced inside a batch of indicator expressions.

    Looks for ``${name}`` and bare ``word`` tokens that look like identifiers.
    Over-matches on purpose — losing a real column would silently break an
    indicator, whereas keeping an extra one is a drop-step decision.
    """

    import re

    found: set[str] = set()
    token = re.compile(r"\$\{([A-Za-z_][\w./]*)\}|\b([A-Za-z_][\w./]*)\b")
    reserved = {"and", "or", "not", "in", "True", "False", "None", "selected", "isna", "between"}
    for expr in expressions:
        if not expr:
            continue
        for m in token.finditer(expr):
            name = m.group(1) or m.group(2)
            if name and name not in reserved and not name.isdigit():
                found.add(name)
    return found


def minimise_columns(
    df: pd.DataFrame,
    keep: Iterable[str],
    always_keep: Iterable[str] = (),
) -> pd.DataFrame:
    """Return ``df`` restricted to ``keep`` plus ``always_keep`` that actually exist.

    The result preserves the original column order. Columns requested but not
    present are silently ignored — the scan report surfaces that mismatch
    elsewhere and we don't want a protect step to crash the pipeline.
    """

    wanted = set(keep) | set(always_keep)
    cols = [c for c in df.columns if c in wanted]
    return df.loc[:, cols].copy()
