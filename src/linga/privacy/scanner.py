"""PII and sensitive-field scanner.

Runs three checks per column:

1. Column-name keyword match against ``sensitive_keywords.yml``.
2. Value sampling (up to ``sample_size``) against :mod:`linga.privacy.patterns`.
3. Free-text / geopoint heuristics.

Each column is assigned a risk level — ``high``, ``medium`` or ``low`` — and a
plain-language suggested action. Raw values **never** appear in the report.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from linga.data import SENSITIVE_KEYWORDS_YML
from linga.privacy.patterns import (
    DOB_RE,
    EMAIL_RE,
    GEOPOINT_RE,
    GPS_PAIR_RE,
    NRC_RE,
    matches_phone,
)


@dataclass
class ColumnScan:
    name: str
    risk: str  # 'high' | 'medium' | 'low'
    signals: list[str] = field(default_factory=list)
    suggested_action: str = ""


@dataclass
class ScanReport:
    columns: list[ColumnScan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"columns": [asdict(c) for c in self.columns]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def high_risk_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.risk == "high"]


def load_sensitive_keywords(path: Path | None = None) -> dict[str, list[str]]:
    path = path or SENSITIVE_KEYWORDS_YML
    data: dict[str, list[str]] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: [str(x).lower() for x in v] for k, v in data.items()}


def scan_dataframe(
    df: pd.DataFrame,
    sample_size: int = 500,
    sensitive_keywords: dict[str, list[str]] | None = None,
) -> ScanReport:
    kwmap = sensitive_keywords or load_sensitive_keywords()
    report = ScanReport()
    for col in df.columns:
        signals: list[str] = []
        lower = str(col).lower()

        # (1) column-name heuristics
        for category, keywords in kwmap.items():
            if any(k in lower for k in keywords):
                signals.append(f"name:{category}")

        # (2) value sampling
        series = df[col].dropna().astype(str)
        sample = series.head(sample_size)
        if sample.empty:
            report.columns.append(
                ColumnScan(
                    name=str(col),
                    risk=_derive_risk(signals),
                    signals=signals,
                    suggested_action=_suggest(signals),
                )
            )
            continue

        if sample.str.contains(NRC_RE).any():
            signals.append("value:nrc")
        if sample.map(matches_phone).any():
            signals.append("value:phone")
        if sample.str.contains(EMAIL_RE).any():
            signals.append("value:email")
        if sample.str.contains(DOB_RE).any():
            signals.append("value:dob")
        if sample.str.match(GEOPOINT_RE).any():
            signals.append("value:geopoint")
        elif sample.str.match(GPS_PAIR_RE).any():
            signals.append("value:gps_coordinate")

        risk = _derive_risk(signals)
        report.columns.append(
            ColumnScan(
                name=str(col),
                risk=risk,
                signals=signals,
                suggested_action=_suggest(signals),
            )
        )
    return report


def _derive_risk(signals: list[str]) -> str:
    high_markers = {
        "name:identifiers",
        "name:biometrics",
        "value:nrc",
        "value:phone",
        "value:email",
        "value:geopoint",
        "value:dob",
    }
    medium_markers = {
        "name:health",
        "name:hiv",
        "name:disability",
        "name:sex",
        "name:marital_status",
        "name:ethnicity",
        "name:religion",
        "name:political_opinion",
        "value:gps_coordinate",
    }
    if any(s in high_markers for s in signals):
        return "high"
    if any(s in medium_markers for s in signals):
        return "medium"
    return "low"


def _suggest(signals: list[str]) -> str:
    if not signals:
        return "keep"
    if any(s.startswith("value:nrc") or s.startswith("value:phone") for s in signals):
        return "pseudonymise or drop"
    if "value:email" in signals:
        return "drop"
    if "value:geopoint" in signals or "value:gps_coordinate" in signals:
        return "round coordinates or generalise to admin area"
    if any(s.startswith("name:identifiers") for s in signals):
        return "pseudonymise or drop"
    if any(s.startswith("name:") for s in signals):
        return "retain only if required by logframe"
    return "review"
