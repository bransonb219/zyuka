"""Tests for zyuka.warehouse.snapshot (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from zyuka.warehouse.snapshot import (
    build_snapshot,
    compare_snapshots,
    load_snapshots,
    save_snapshot,
)


def _baseline_df(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "age": rng.integers(18, 60, size=120),
            "income": rng.normal(100, 20, size=120),
            "region": rng.choice(["north", "south"], size=120),
        }
    )


def test_build_and_save_snapshot_round_trips(tmp_path: Path) -> None:
    df = _baseline_df()
    snap = build_snapshot("baseline", df)
    out = save_snapshot(snap, tmp_path)
    assert out.exists()

    loaded = load_snapshots(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].round_name == "baseline"
    assert loaded[0].n_rows == 120
    assert loaded[0].n_cols == 3


def test_compare_snapshots_detects_added_dropped_and_drift(tmp_path: Path) -> None:
    baseline = _baseline_df(seed=0)
    midline = baseline.drop(columns=["region"]).assign(
        income=baseline["income"] + 30,
        household_size=np.random.default_rng(1).integers(1, 8, size=len(baseline)),
    )
    s1 = build_snapshot("baseline", baseline)
    s2 = build_snapshot("midline", midline)
    save_snapshot(s1, tmp_path)
    save_snapshot(s2, tmp_path)

    loaded = load_snapshots(tmp_path)
    comparison = compare_snapshots(loaded)

    assert comparison.rounds == ["baseline", "midline"]
    assert "household_size" in comparison.columns_added["midline"]
    assert "region" in comparison.columns_dropped["midline"]
    drifting = {row["column"] for row in comparison.numeric_mean_drift}
    assert "income" in drifting


def test_compare_single_snapshot_is_empty() -> None:
    df = _baseline_df()
    snap = build_snapshot("baseline", df)
    comp = compare_snapshots([snap])
    assert comp.rounds == ["baseline"]
    assert comp.missingness_drift == []
    assert comp.numeric_mean_drift == []


def test_missingness_drift_captures_column_with_increasing_nans(tmp_path: Path) -> None:
    baseline = _baseline_df()
    midline = baseline.copy()
    midline.loc[midline.index[:40], "income"] = np.nan  # 33% missing

    s1 = build_snapshot("baseline", baseline)
    s2 = build_snapshot("midline", midline)
    save_snapshot(s1, tmp_path)
    save_snapshot(s2, tmp_path)

    comparison = compare_snapshots(load_snapshots(tmp_path))
    rows = {row["column"]: row for row in comparison.missingness_drift}
    assert "income" in rows
    assert rows["income"]["delta_pct"] > 20
