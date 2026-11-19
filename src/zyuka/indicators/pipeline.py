"""Glue that runs the indicator engine across every round + the logframe.

This module is what the ``zyuka compute`` and ``zyuka run`` commands call. It
loads the project config + logframe, discovers each protected round CSV, runs
the engine with disaggregations, and builds the longitudinal view.

Output is a :class:`IndicatorResults` dataclass with a ``to_json`` helper
that the HTML/Excel reporters consume. Results are deliberately a plain tree
of dicts so they survive serialisation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from zyuka.config import IndicatorDef, LogframeConfig, ZyukaConfig, load_logframe, load_zyuka_config
from zyuka.errors import IndicatorError
from zyuka.indicators.disaggregate import DisaggregatedResult, disaggregate_indicator
from zyuka.indicators.engine import IndicatorValue
from zyuka.indicators.evaluation import (
    Interval,
    equity_gap,
    t_interval,
    two_proportion_z_test,
    velocity,
    welch_t_test_summary,
    wilson_interval,
)
from zyuka.indicators.longitudinal import LongitudinalPoint, build_series
from zyuka.indicators.validate import ValidationResult, validate_logframe


@dataclass
class IndicatorResults:
    rounds: list[str] = field(default_factory=list)
    indicators: list[dict[str, Any]] = field(default_factory=list)
    validation: list[dict[str, str]] = field(default_factory=list)
    oecd_dac: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": self.rounds,
            "indicators": self.indicators,
            "validation": self.validation,
            "oecd_dac": self.oecd_dac,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def _load_rounds(rounds_dir: Path) -> dict[str, pd.DataFrame]:
    rounds: dict[str, pd.DataFrame] = {}
    for csv in sorted(Path(rounds_dir).glob("*.csv")):
        stem = csv.stem
        # Strip "protected_" or "survey_" prefix if present.
        for prefix in ("protected_survey_", "protected_", "survey_"):
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]
                break
        rounds[stem] = pd.read_csv(csv)
    return rounds


def _serialise_long(points: list[LongitudinalPoint]) -> list[dict[str, Any]]:
    return [
        {
            "round": p.round,
            "value": p.value,
            "target": p.target,
            "change_from_baseline": p.change_from_baseline,
            "percent_of_target": p.percent_of_target,
            "status": p.status,
        }
        for p in points
    ]


def _interval(indicator: IndicatorDef, iv: IndicatorValue) -> Interval | None:
    if iv.value is None:
        return None
    if indicator.type in {"proportion", "ratio"}:
        if iv.numerator is None or iv.denominator is None:
            return None
        return wilson_interval(iv.numerator, iv.denominator)
    if indicator.type == "mean" and iv.std is not None and iv.numerator:
        return t_interval(float(iv.value), float(iv.std), int(iv.numerator))
    return None


def _equity_gaps(indicator: IndicatorDef, disagg: DisaggregatedResult) -> dict[str, dict[str, Any]]:
    gaps: dict[str, dict[str, Any]] = {}
    for col, per_value in disagg.by_column.items():
        values = {val: iv.value for val, iv in per_value.items()}
        gap = equity_gap(values)
        if gap:
            gaps[col] = gap
    return gaps


def _pre_post(
    indicator: IndicatorDef,
    per_round_values: dict[str, IndicatorValue],
) -> dict[str, float] | None:
    if len(per_round_values) < 2:
        return None
    rounds = list(per_round_values)
    first, last = per_round_values[rounds[0]], per_round_values[rounds[-1]]
    if first.value is None or last.value is None:
        return None
    if indicator.type in {"proportion", "ratio"}:
        if first.numerator is None or first.denominator is None:
            return None
        if last.numerator is None or last.denominator is None:
            return None
        return two_proportion_z_test(
            first.numerator, first.denominator, last.numerator, last.denominator
        )
    if indicator.type == "mean":
        if first.std is None or last.std is None:
            return None
        if first.numerator is None or last.numerator is None:
            return None
        return welch_t_test_summary(
            float(first.value),
            first.std,
            int(first.numerator),
            float(last.value),
            last.std,
            int(last.numerator),
        )
    return None


def _evaluation_payload(
    indicator: IndicatorDef,
    per_round_values: dict[str, IndicatorValue],
    disagg_by_round: dict[str, DisaggregatedResult],
    long_points: list[LongitudinalPoint],
) -> dict[str, Any]:
    intervals: dict[str, dict[str, float]] = {}
    for round_name, iv in per_round_values.items():
        interval = _interval(indicator, iv)
        if interval:
            intervals[round_name] = interval.to_dict()

    equity: dict[str, dict[str, dict[str, Any]]] = {}
    for round_name, disagg in disagg_by_round.items():
        gaps = _equity_gaps(indicator, disagg)
        if gaps:
            equity[round_name] = gaps

    target_for_vel = indicator.targets.get(long_points[-1].round) if long_points else None
    traj = velocity([p.value for p in long_points], target=target_for_vel)
    pre_post = _pre_post(indicator, per_round_values)

    return {
        "confidence_intervals": intervals,
        "equity_gaps": equity,
        "trajectory": traj,
        "pre_post": pre_post,
        "means_of_verification": indicator.means_of_verification,
        "assumptions": indicator.assumptions,
    }


def compute_from_rounds(
    logframe: LogframeConfig,
    rounds: dict[str, pd.DataFrame],
    config: ZyukaConfig | None = None,
) -> IndicatorResults:
    """Run the engine for each indicator across every round. Pure function."""

    validation = validate_logframe(logframe, rounds)
    results = IndicatorResults(
        rounds=list(rounds.keys()),
        validation=[
            {"code": iss.code, "message": iss.message, "suggestion": iss.suggestion}
            for iss in validation.issues
        ],
        oecd_dac=({} if logframe.oecd_dac.is_empty() else logframe.oecd_dac.model_dump()),
    )

    thresholds = config.traffic_light if config is not None else None

    for indicator in logframe.all_indicators():
        per_round: dict[str, Any] = {}
        per_round_values: dict[str, IndicatorValue] = {}
        disagg_by_round: dict[str, DisaggregatedResult] = {}
        for round_name, df in rounds.items():
            try:
                disagg = disaggregate_indicator(df, indicator)
            except IndicatorError as exc:
                per_round[round_name] = {"error": str(exc)}
                continue
            per_round_values[round_name] = disagg.overall
            disagg_by_round[round_name] = disagg
            per_round[round_name] = {
                "overall": asdict(disagg.overall),
                "by": {
                    col: {val: asdict(iv) for val, iv in by_val.items()}
                    for col, by_val in disagg.by_column.items()
                },
            }

        long_points = build_series(indicator, per_round_values, thresholds=thresholds)
        evaluation = _evaluation_payload(indicator, per_round_values, disagg_by_round, long_points)
        results.indicators.append(
            {
                "code": indicator.code,
                "name": indicator.name,
                "type": indicator.type,
                "unit": indicator.unit,
                "per_round": per_round,
                "longitudinal": _serialise_long(long_points),
                "evaluation": evaluation,
            }
        )
    return results


def compute_project_indicators(
    project_dir: Path,
    rounds_dir: Path,
) -> IndicatorResults:
    """Load everything from disk and hand off to :func:`compute_from_rounds`."""

    project_dir = Path(project_dir)
    rounds_dir = Path(rounds_dir)

    cfg_path = project_dir / "zyuka.yml"
    lf_path = project_dir / "logframe.yml"
    config = load_zyuka_config(cfg_path) if cfg_path.exists() else None
    logframe = load_logframe(lf_path)
    rounds = _load_rounds(rounds_dir)
    return compute_from_rounds(logframe, rounds, config=config)


def validate_only(logframe_path: Path, rounds: dict[str, pd.DataFrame]) -> ValidationResult:
    logframe = load_logframe(logframe_path)
    return validate_logframe(logframe, rounds)
