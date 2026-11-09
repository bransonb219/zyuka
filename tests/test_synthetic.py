"""Tests for the synthetic data generator."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from zyuka.synthetic import ROUND_NAMES, SyntheticOptions, generate_round, write_rounds

_NRC_RE = re.compile(r"^\d{6}/\d{2}/\d$")
_PHONE_RE = re.compile(r"^09[67]\d{8}$")


def test_round_names() -> None:
    assert ROUND_NAMES == ("baseline", "midline", "endline")


def test_generate_round_shape_and_tag() -> None:
    df = generate_round("baseline", SyntheticOptions(rows_per_round=30))
    assert len(df) >= 30  # synthetic injects a duplicate
    assert (df["round"] == "baseline").all()
    assert {"nrc", "phone", "sex", "province", "gps_lat", "gps_lon"} <= set(df.columns)


def test_generate_round_deterministic() -> None:
    opts = SyntheticOptions(rows_per_round=20, seed=1234)
    df1 = generate_round("midline", opts)
    df2 = generate_round("midline", opts)
    pd.testing.assert_frame_equal(df1, df2)


def test_generated_nrcs_and_phones_match_patterns() -> None:
    df = generate_round("baseline", SyntheticOptions(rows_per_round=50))
    assert df["nrc"].astype(str).str.match(_NRC_RE).all()
    assert df["phone"].astype(str).str.match(_PHONE_RE).all()


def test_pid_seed_is_stable_across_rounds() -> None:
    opts = SyntheticOptions(rows_per_round=10)
    baseline = generate_round("baseline", opts)
    midline = generate_round("midline", opts)
    # Same pid_seed values appear in both rounds in the same order (for linkage).
    assert list(baseline["pid_seed"])[:10] == list(midline["pid_seed"])[:10]


def test_write_rounds_creates_three_csvs(tmp_path: Path) -> None:
    paths = write_rounds(tmp_path, SyntheticOptions(rows_per_round=10))
    assert set(paths) == set(ROUND_NAMES)
    for p in paths.values():
        assert p.exists() and p.suffix == ".csv"
