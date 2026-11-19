"""Evaluation-grade enrichments for indicator results (Track B).

Six self-contained helpers that layer on top of the existing engine:

* :func:`wilson_interval` — binomial confidence interval for proportions.
* :func:`t_interval` — t-based CI for a sample mean.
* :func:`equity_gap` — spread between the best- and worst-performing
  disaggregation group.
* :func:`velocity` — slope through the longitudinal series and a simple
  projection to the final round.
* :func:`two_proportion_z_test` — pre/post significance for ``proportion``
  indicators.
* :func:`welch_t_test_summary` — pre/post significance for ``mean``
  indicators using summary statistics (mean, std, n).

None of these reach for the raw data; everything is computed from
summary statistics the engine already has. That keeps the layer safe
for protected / aggregated datasets and side-steps re-reading CSVs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

try:
    from scipy import stats as _stats

    _HAS_SCIPY = True
except ImportError:  # pragma: no cover - scipy is a hard dep, kept defensive
    _HAS_SCIPY = False


@dataclass(frozen=True)
class Interval:
    """A two-sided confidence interval."""

    lower: float
    upper: float
    alpha: float

    def to_dict(self) -> dict[str, float]:
        return {"lower": self.lower, "upper": self.upper, "alpha": self.alpha}


def _z_critical(alpha: float) -> float:
    if _HAS_SCIPY:
        return float(_stats.norm.ppf(1 - alpha / 2))
    if abs(alpha - 0.05) < 1e-9:
        return 1.959963984540054
    if abs(alpha - 0.10) < 1e-9:
        return 1.6448536269514722
    if abs(alpha - 0.01) < 1e-9:
        return 2.5758293035489004
    raise ValueError("alpha must be 0.01, 0.05 or 0.10 without scipy installed.")


def wilson_interval(successes: int, trials: int, alpha: float = 0.05) -> Interval | None:
    """Wilson score interval for a proportion.

    Robust at small ``trials`` and near 0 / 1 — the standard practice
    when reporting indicator coverage with a small denominator.
    """

    if trials <= 0:
        return None
    z = _z_critical(alpha)
    phat = successes / trials
    denom = 1 + z**2 / trials
    centre = (phat + z**2 / (2 * trials)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / trials + z**2 / (4 * trials**2))) / denom
    return Interval(lower=max(0.0, centre - half), upper=min(1.0, centre + half), alpha=alpha)


def t_interval(mean: float, std: float, n: int, alpha: float = 0.05) -> Interval | None:
    """Two-sided t confidence interval for the mean.

    Falls back to ``None`` when ``n < 2`` or ``std`` is zero. Requires
    scipy for the exact critical value (always present as a hard dep).
    """

    if n < 2 or std <= 0:
        return None
    if not _HAS_SCIPY:
        return None
    t = float(_stats.t.ppf(1 - alpha / 2, df=n - 1))
    se = std / math.sqrt(n)
    return Interval(lower=mean - t * se, upper=mean + t * se, alpha=alpha)


def equity_gap(values_by_group: dict[str, float | int | None]) -> dict[str, Any] | None:
    """Max minus min across disaggregation groups.

    Returns the gap plus the best / worst group labels so a reviewer can
    name the gap in plain language ("girls vs. boys: 14pp").
    """

    numeric = {k: float(v) for k, v in values_by_group.items() if v is not None}
    if len(numeric) < 2:
        return None
    best_group = max(numeric, key=lambda k: numeric[k])
    worst_group = min(numeric, key=lambda k: numeric[k])
    return {
        "gap": numeric[best_group] - numeric[worst_group],
        "best_group": best_group,
        "best_value": numeric[best_group],
        "worst_group": worst_group,
        "worst_value": numeric[worst_group],
        "n_groups": len(numeric),
    }


def velocity(
    values: list[float | int | None],
    target: float | None = None,
) -> dict[str, Any] | None:
    """Simple linear fit through the per-round values.

    Returns the per-round slope, an interpolated prediction one round
    ahead and (when ``target`` is given) the number of extra rounds
    required to reach the target at the current slope. All values are
    treated as equally-spaced points; irregular cadences should be
    interpreted carefully.
    """

    points = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / denom
    intercept = mean_y - slope * mean_x
    last_x = xs[-1]
    next_pred = intercept + slope * (last_x + 1)
    result: dict[str, Any] = {
        "slope_per_round": slope,
        "next_round_projection": next_pred,
    }
    if target is not None and slope != 0:
        remaining = (target - ys[-1]) / slope
        if math.isfinite(remaining) and remaining >= 0:
            result["rounds_to_target"] = remaining
    return result


def two_proportion_z_test(x1: int, n1: int, x2: int, n2: int) -> dict[str, float] | None:
    """Two-sample z-test comparing two proportions (two-sided)."""

    if min(n1, n2) == 0:
        return None
    p1, p2 = x1 / n1, x2 / n2
    pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    z = (p2 - p1) / se
    if _HAS_SCIPY:
        p = 2 * (1 - float(_stats.norm.cdf(abs(z))))
    else:
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"z": z, "p_value": p, "diff": p2 - p1}


def welch_t_test_summary(
    mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int
) -> dict[str, float] | None:
    """Welch's t-test from summary statistics."""

    if n1 < 2 or n2 < 2 or std1 <= 0 or std2 <= 0:
        return None
    se = math.sqrt(std1**2 / n1 + std2**2 / n2)
    if se == 0:
        return None
    t = (mean2 - mean1) / se
    df_num = (std1**2 / n1 + std2**2 / n2) ** 2
    df_den = (std1**2 / n1) ** 2 / (n1 - 1) + (std2**2 / n2) ** 2 / (n2 - 1)
    df = df_num / df_den if df_den > 0 else float("nan")
    if _HAS_SCIPY and math.isfinite(df):
        p = 2 * (1 - float(_stats.t.cdf(abs(t), df=df)))
    else:
        return None
    return {"t": t, "df": df, "p_value": p, "diff": mean2 - mean1}
