"""Shared fixtures. Synthetic data only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from zyuka.synthetic import SyntheticOptions, generate_round, write_rounds


@pytest.fixture(scope="session")
def small_options() -> SyntheticOptions:
    return SyntheticOptions(rows_per_round=40, seed=42)


@pytest.fixture
def baseline_df(small_options: SyntheticOptions) -> pd.DataFrame:
    return generate_round("baseline", small_options)


@pytest.fixture
def three_round_paths(tmp_path: Path, small_options: SyntheticOptions) -> dict[str, Path]:
    return write_rounds(tmp_path / "rounds", small_options)
