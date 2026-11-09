"""Shared helpers for the CLI commands that run parts of the pipeline.

Right now only ``protect_dataframe`` lives here — it's imported by both the
``zyuka protect`` command and the full ``zyuka run`` pipeline so the two
can't drift apart. The function returns a *new* DataFrame plus a JSON
manifest describing every column's treatment.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from zyuka.config import LogframeConfig, ZyukaConfig, load_logframe, load_zyuka_config
from zyuka.privacy.generalise import (
    drop_free_text,
    generalise_date_to_month,
    generalise_dob,
    generalise_gps,
)
from zyuka.privacy.minimise import extract_referenced_columns, minimise_columns
from zyuka.privacy.pseudonymise import pseudonymise_series
from zyuka.privacy.scanner import ScanReport, scan_dataframe
from zyuka.security.keys import Key, load_key

ALWAYS_KEEP: tuple[str, ...] = (
    "_uuid",
    "instanceID",
    "pid_seed",
    "round",
    "enumerator_id",
    "start",
    "end",
    "age",
    "sex",
    "province",
    "district",
)


FREE_TEXT_HINTS: tuple[str, ...] = ("notes", "comments", "other_specify", "address_text")


def _is_gps_column(name: str) -> bool:
    lower = name.lower()
    return any(tok in lower for tok in ("gps", "lat", "lon", "geopoint", "coord"))


def _is_dob_column(name: str) -> bool:
    return "dob" in name.lower() or "birth" in name.lower()


def _is_date_column(name: str) -> bool:
    lower = name.lower()
    return any(tok in lower for tok in ("date", "day")) and not _is_dob_column(name)


def _is_identifier(name: str, scan: ScanReport) -> bool:
    for col in scan.columns:
        if col.name == name and (
            "value:nrc" in col.signals
            or "value:phone" in col.signals
            or "name:identifiers" in col.signals
        ):
            return True
    return False


def protect_dataframe(
    df: pd.DataFrame,
    project_dir: Path | None = None,
    config: ZyukaConfig | None = None,
    logframe: LogframeConfig | None = None,
    key: Key | None = None,
) -> tuple[pd.DataFrame, str]:
    """Return ``(protected_df, manifest_json)`` for the given frame.

    The default behaviour, when called without a logframe, is to keep every
    column present and apply column-type transforms (pseudonymise obvious
    identifiers, generalise GPS/DOB, drop free text). With a logframe, the
    keep-list is intersected with ``ALWAYS_KEEP`` so unused columns are
    dropped first.
    """

    if config is None and project_dir is not None:
        cfg_path = Path(project_dir) / "zyuka.yml"
        if cfg_path.exists():
            config = load_zyuka_config(cfg_path)
    if logframe is None and project_dir is not None:
        lf_path = Path(project_dir) / "logframe.yml"
        if lf_path.exists():
            logframe = load_logframe(lf_path)
    if key is None and config is not None:
        key = load_key(config.key_path)

    scan = scan_dataframe(df)
    treatments: dict[str, str] = {}

    if logframe is not None:
        exprs: list[str] = []
        for ind in logframe.all_indicators():
            exprs.append(ind.numerator)
            if ind.denominator:
                exprs.append(ind.denominator)
            exprs.extend(ind.disaggregations)
        referenced = extract_referenced_columns(exprs)
        allowlist = list(config.protection.keep_columns) if config else []
        minimised = minimise_columns(df, keep=referenced | set(allowlist), always_keep=ALWAYS_KEEP)
        for col in df.columns:
            if col not in minimised.columns:
                treatments[col] = "dropped (not referenced by logframe)"
        working = minimised
    else:
        working = df.copy()

    drop_free = config.protection.drop_free_text if config else True
    gps_decimals = config.protection.gps_decimals if config else 1

    for col in list(working.columns):
        # Order matters: generalisation rules win over blunt pseudonymisation
        # for columns that happen to match multiple heuristics (e.g. gps_lat
        # matches both the GPS and the generic 'name:identifiers' signal).
        if drop_free and any(hint in col.lower() for hint in FREE_TEXT_HINTS):
            working[col] = drop_free_text(working[col])
            treatments[col] = "free text cleared"
            continue

        if _is_gps_column(col):
            try:
                working[col] = generalise_gps(working[col].astype(float), decimals=gps_decimals)
                treatments[col] = f"GPS rounded to {gps_decimals} decimal(s)"
            except (TypeError, ValueError):
                treatments[col] = "GPS column left as-is (non-numeric)"
            continue

        if _is_dob_column(col):
            working[col] = generalise_dob(working[col])
            treatments[col] = "DOB → age band"
            continue

        if _is_date_column(col):
            working[col] = generalise_date_to_month(working[col])
            treatments[col] = "date → year-month"
            continue

        if _is_identifier(col, scan):
            if key is None:
                working[col] = ""
                treatments[col] = "identifier dropped (no key configured)"
            else:
                working[col] = pseudonymise_series(working[col], key.material)
                treatments[col] = "pseudonymised (HMAC-SHA256)"
            continue

        treatments.setdefault(col, "kept")

    manifest: dict[str, Any] = {
        "columns": [
            {"name": c, "treatment": treatments.get(c, "kept")} for c in sorted(treatments)
        ],
        "key_fingerprint": key.fingerprint if key is not None else None,
        "row_count": len(working),
    }
    return working, json.dumps(manifest, indent=2)


def columns_from_expressions(expressions: Iterable[str]) -> set[str]:
    """Public re-export used by the indicator validator."""

    return extract_referenced_columns(expressions)
