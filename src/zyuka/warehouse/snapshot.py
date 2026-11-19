"""Persist and compare per-round dataset snapshots.

A :class:`Snapshot` is a JSON-safe summary of one round after cleaning
and protection: how many rows, which columns, their missingness, the
distribution shape of each numeric column, and optionally the indicator
values that were computed. Snapshots live alongside the other outputs
under ``<project>/outputs/warehouse/`` and are append-only — a fresh
pipeline run overwrites the round's file with the latest state.

The shape is intentionally stripped: no raw rows, no PII, no
untransformed samples. Everything surfaced in the report is a count, a
moment, or a hash. Cross-round drift is built on top of this so the
report can answer "what changed between baseline and endline?" without
re-reading the protected CSVs.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from zyuka import __version__
from zyuka.analysis.eda import DatasetProfile, profile_dataframe

SNAPSHOT_SUFFIX = ".json"
DRIFT_TOP_N = 10


@dataclass
class Snapshot:
    """One per-round dataset snapshot."""

    round_name: str
    generated_at: str
    zyuka_version: str
    n_rows: int
    n_cols: int
    source_sha256: str
    profile: dict[str, Any] = field(default_factory=dict)
    indicator_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    analyses: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_name": self.round_name,
            "generated_at": self.generated_at,
            "zyuka_version": self.zyuka_version,
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "source_sha256": self.source_sha256,
            "profile": self.profile,
            "indicator_values": self.indicator_values,
            "analyses": self.analyses,
        }


@dataclass
class SnapshotComparison:
    """Drift between two or more snapshots (chronologically ordered)."""

    rounds: list[str] = field(default_factory=list)
    columns_added: dict[str, list[str]] = field(default_factory=dict)
    columns_dropped: dict[str, list[str]] = field(default_factory=dict)
    row_counts: dict[str, int] = field(default_factory=dict)
    missingness_drift: list[dict[str, Any]] = field(default_factory=list)
    numeric_mean_drift: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": self.rounds,
            "columns_added": self.columns_added,
            "columns_dropped": self.columns_dropped,
            "row_counts": self.row_counts,
            "missingness_drift": self.missingness_drift,
            "numeric_mean_drift": self.numeric_mean_drift,
        }


def _sha256(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(",".join(df.columns.astype(str)).encode("utf-8"))
    h.update(str(df.shape).encode("utf-8"))
    for col in df.columns:
        series = df[col]
        h.update(f"{col}:{series.dtype}:{int(series.isna().sum())}".encode())
    return h.hexdigest()


def build_snapshot(
    round_name: str,
    df: pd.DataFrame,
    indicator_values: dict[str, dict[str, Any]] | None = None,
    analyses: list[dict[str, Any]] | None = None,
    profile: DatasetProfile | None = None,
) -> Snapshot:
    """Assemble a :class:`Snapshot` from a cleaned/protected round."""

    profile = profile or profile_dataframe(df)
    return Snapshot(
        round_name=round_name,
        generated_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        zyuka_version=__version__,
        n_rows=int(df.shape[0]),
        n_cols=int(df.shape[1]),
        source_sha256=_sha256(df),
        profile=profile.to_dict(),
        indicator_values=dict(indicator_values or {}),
        analyses=list(analyses or []),
    )


def save_snapshot(snapshot: Snapshot, warehouse_dir: Path) -> Path:
    """Write ``snapshot`` to ``<warehouse_dir>/<round>.json`` and return the path."""

    warehouse_dir = Path(warehouse_dir)
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    out = warehouse_dir / f"{snapshot.round_name}{SNAPSHOT_SUFFIX}"
    out.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
    return out


def load_snapshots(warehouse_dir: Path) -> list[Snapshot]:
    """Load snapshots from disk ordered by ``generated_at``."""

    warehouse_dir = Path(warehouse_dir)
    if not warehouse_dir.exists():
        return []
    snaps: list[Snapshot] = []
    for path in warehouse_dir.glob(f"*{SNAPSHOT_SUFFIX}"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        snaps.append(
            Snapshot(
                round_name=str(payload.get("round_name", path.stem)),
                generated_at=str(payload.get("generated_at", "")),
                zyuka_version=str(payload.get("zyuka_version", "")),
                n_rows=int(payload.get("n_rows", 0)),
                n_cols=int(payload.get("n_cols", 0)),
                source_sha256=str(payload.get("source_sha256", "")),
                profile=dict(payload.get("profile", {}) or {}),
                indicator_values=dict(payload.get("indicator_values", {}) or {}),
                analyses=list(payload.get("analyses", []) or []),
            )
        )
    snaps.sort(key=lambda s: s.generated_at)
    return snaps


def _column_lookup(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    cols = snapshot.profile.get("columns", []) or []
    return {str(c.get("name", "")): c for c in cols if c.get("name")}


def compare_snapshots(snapshots: list[Snapshot]) -> SnapshotComparison:
    """Diff two or more snapshots into column / missingness / mean drift tables."""

    comp = SnapshotComparison(rounds=[s.round_name for s in snapshots])
    if len(snapshots) < 2:
        return comp

    for snap in snapshots:
        comp.row_counts[snap.round_name] = snap.n_rows

    lookups = [(s.round_name, _column_lookup(s)) for s in snapshots]
    for (_prev_round, prev), (curr_round, curr) in itertools.pairwise(lookups):
        prev_cols = set(prev.keys())
        curr_cols = set(curr.keys())
        added = sorted(curr_cols - prev_cols)
        dropped = sorted(prev_cols - curr_cols)
        comp.columns_added[curr_round] = added
        comp.columns_dropped[curr_round] = dropped

    missing_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []
    all_columns = sorted({name for _, cols in lookups for name in cols})
    for name in all_columns:
        missingness = {}
        means = {}
        for round_name, cols in lookups:
            info = cols.get(name)
            if info is None:
                continue
            missingness[round_name] = float(info.get("missing_pct", 0.0))
            if info.get("kind") == "numeric" and info.get("mean") is not None:
                means[round_name] = float(info["mean"])
        if len(missingness) >= 2:
            delta = max(missingness.values()) - min(missingness.values())
            if delta > 0:
                missing_rows.append(
                    {"column": name, "missing_pct": missingness, "delta_pct": float(delta)}
                )
        if len(means) >= 2:
            delta = max(means.values()) - min(means.values())
            if delta != 0:
                numeric_rows.append({"column": name, "mean": means, "delta": float(delta)})
    missing_rows.sort(key=lambda r: r["delta_pct"], reverse=True)
    numeric_rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    comp.missingness_drift = missing_rows[:DRIFT_TOP_N]
    comp.numeric_mean_drift = numeric_rows[:DRIFT_TOP_N]
    return comp
