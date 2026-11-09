"""Longitudinal view: change from baseline + traffic-light status.

Given per-round values for the same indicator, produce:

- ``change_from_baseline`` — absolute difference from baseline to this round.
- ``percent_of_target`` — rounded to one decimal; uses the round's target.
- ``status`` — ``"on_track"`` / ``"at_risk"`` / ``"off_track"`` based on the
  configured thresholds. ``on_track`` means the value meets or exceeds
  ``thresholds.on_track`` percent of target. ``at_risk`` is between
  ``thresholds.at_risk`` and ``thresholds.on_track``. Below that, ``off_track``.

Decreasing indicators (e.g. "proportion in poverty") are handled by giving the
target a smaller value than the baseline; the engine compares against the
target directly, so no extra flag is needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from zyuka.config import IndicatorDef, TrafficLightStatus, TrafficLightThresholds
from zyuka.indicators.engine import IndicatorValue


@dataclass(frozen=True)
class LongitudinalPoint:
    round: str
    value: float | int | None
    target: float | None
    change_from_baseline: float | None
    percent_of_target: float | None
    status: TrafficLightStatus | None


def _percent_of_target(value: float | int | None, target: float | None) -> float | None:
    if value is None or target is None or target == 0:
        return None
    return round((float(value) / float(target)) * 100.0, 1)


def _status(pct: float | None, thresholds: TrafficLightThresholds) -> TrafficLightStatus | None:
    if pct is None:
        return None
    if pct >= thresholds.on_track:
        return "on_track"
    if pct >= thresholds.at_risk:
        return "at_risk"
    return "off_track"


def build_series(
    indicator: IndicatorDef,
    per_round: dict[str, IndicatorValue],
    thresholds: TrafficLightThresholds | None = None,
) -> list[LongitudinalPoint]:
    """Return one point per round in ``per_round``'s iteration order."""

    thresholds = thresholds or TrafficLightThresholds()
    baseline_value: float | int | None = indicator.baseline
    if baseline_value is None:
        for name in ("baseline", "Baseline"):
            if name in per_round:
                baseline_value = per_round[name].value
                break

    points: list[LongitudinalPoint] = []
    for round_name, result in per_round.items():
        target = indicator.targets.get(round_name)
        change = None
        if result.value is not None and baseline_value is not None:
            try:
                change = float(result.value) - float(baseline_value)
            except (TypeError, ValueError):
                change = None
        pct = _percent_of_target(result.value, target)
        status = _status(pct, thresholds)
        points.append(
            LongitudinalPoint(
                round=round_name,
                value=result.value,
                target=target,
                change_from_baseline=change,
                percent_of_target=pct,
                status=status,
            )
        )
    return points
