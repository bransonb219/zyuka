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

from zyuka.config import LogframeConfig, ZyukaConfig, load_logframe, load_zyuka_config
from zyuka.errors import IndicatorError
from zyuka.indicators.disaggregate import disaggregate_indicator
from zyuka.indicators.longitudinal import LongitudinalPoint, build_series
from zyuka.indicators.validate import ValidationResult, validate_logframe


@dataclass
class IndicatorResults:
    rounds: list[str] = field(default_factory=list)
    indicators: list[dict[str, Any]] = field(default_factory=list)
    validation: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": self.rounds,
            "indicators": self.indicators,
            "validation": self.validation,
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
    )

    thresholds = config.traffic_light if config is not None else None

    for indicator in logframe.all_indicators():
        per_round: dict[str, Any] = {}
        per_round_values = {}
        for round_name, df in rounds.items():
            try:
                disagg = disaggregate_indicator(df, indicator)
            except IndicatorError as exc:
                per_round[round_name] = {"error": str(exc)}
                continue
            per_round_values[round_name] = disagg.overall
            per_round[round_name] = {
                "overall": asdict(disagg.overall),
                "by": {
                    col: {val: asdict(iv) for val, iv in by_val.items()}
                    for col, by_val in disagg.by_column.items()
                },
            }

        long_points = build_series(indicator, per_round_values, thresholds=thresholds)
        results.indicators.append(
            {
                "code": indicator.code,
                "name": indicator.name,
                "type": indicator.type,
                "unit": indicator.unit,
                "per_round": per_round,
                "longitudinal": _serialise_long(long_points),
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
