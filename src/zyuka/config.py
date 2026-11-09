"""Configuration models for Zyuka.

All configuration lives in two YAML files:

- ``zyuka.yml`` — organisation, programme, protection settings, key location.
- ``logframe.yml`` — goal, outcomes, outputs and indicators.

Both are parsed into :class:`pydantic.BaseModel` subclasses so the GUI, the CLI
and the pipeline share one validated shape. No network, no file I/O at import
time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from zyuka.errors import ConfigError

IndicatorType = Literal[
    "count",
    "count_unique",
    "proportion",
    "mean",
    "median",
    "sum",
    "ratio",
]

TrafficLightStatus = Literal["on_track", "at_risk", "off_track"]


class ProtectionSettings(BaseModel):
    """How the ``protect`` step should treat PII."""

    model_config = ConfigDict(extra="forbid")

    small_cell_threshold: int = Field(5, ge=1, description="Suppress cells with n < this.")
    gps_decimals: int = Field(1, ge=0, le=6, description="Rounding for GPS coordinates.")
    drop_free_text: bool = Field(True)
    keep_columns: list[str] = Field(default_factory=list, description="Allowlist to keep.")


class TrafficLightThresholds(BaseModel):
    """Thresholds (0-100 percent of target achieved) for traffic-light status."""

    model_config = ConfigDict(extra="forbid")

    on_track: float = Field(80.0, ge=0.0, le=200.0)
    at_risk: float = Field(50.0, ge=0.0, le=200.0)


class ZyukaConfig(BaseModel):
    """Top-level organisation + programme configuration (``zyuka.yml``)."""

    model_config = ConfigDict(extra="forbid")

    organisation: str
    programme: str
    data_controller_contact: str
    retention_days: int = Field(1825, ge=1, description="Default retention: 5 years.")
    key_path: Path = Field(..., description="Absolute path to the key file (outside repo).")
    protection: ProtectionSettings = ProtectionSettings()
    traffic_light: TrafficLightThresholds = TrafficLightThresholds()
    consent_column: str | None = Field(
        None, description="Column where the respondent recorded consent (yes/no)."
    )

    @field_validator("organisation", "programme", "data_controller_contact")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class IndicatorDef(BaseModel):
    """A single logframe indicator."""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    type: IndicatorType
    numerator: str
    denominator: str | None = None
    disaggregations: list[str] = Field(default_factory=list)
    baseline: float | None = None
    targets: dict[str, float] = Field(default_factory=dict)
    unit: str = ""
    data_source: str = ""
    frequency: str = ""


class OutputDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    indicators: list[IndicatorDef] = Field(default_factory=list)


class OutcomeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    indicators: list[IndicatorDef] = Field(default_factory=list)
    outputs: list[OutputDef] = Field(default_factory=list)


class LogframeConfig(BaseModel):
    """Full logframe tree."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    goal_indicators: list[IndicatorDef] = Field(default_factory=list)
    outcomes: list[OutcomeDef] = Field(default_factory=list)

    def all_indicators(self) -> list[IndicatorDef]:
        out: list[IndicatorDef] = list(self.goal_indicators)
        for oc in self.outcomes:
            out.extend(oc.indicators)
            for op in oc.outputs:
                out.extend(op.indicators)
        return out


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(
            f"Configuration file not found: {path}",
            suggest="Run `zyuka init` to create a fresh project.",
        ) from exc
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"Could not parse YAML in {path.name}: {exc}",
            suggest="Open the file in an editor and check indentation and quoting.",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path.name} must contain a YAML mapping at the top level.",
            suggest="The file should begin with key/value pairs, not a list.",
        )
    return data


def load_zyuka_config(path: Path) -> ZyukaConfig:
    """Load and validate ``zyuka.yml``."""

    data = _load_yaml(path)
    try:
        return ZyukaConfig(**data)
    except Exception as exc:
        raise ConfigError(
            f"{path.name} is not valid: {exc}",
            suggest="Compare with the template produced by `zyuka init`.",
        ) from exc


def load_logframe(path: Path) -> LogframeConfig:
    """Load and validate ``logframe.yml``."""

    data = _load_yaml(path)
    try:
        return LogframeConfig(**data)
    except Exception as exc:
        raise ConfigError(
            f"{path.name} is not valid: {exc}",
            suggest="See docs/logframe-guide.md for the expected structure.",
        ) from exc
