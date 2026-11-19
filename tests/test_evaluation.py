"""Tests for zyuka.indicators.evaluation (Track B)."""

from __future__ import annotations

import pytest

from zyuka.indicators.evaluation import (
    Interval,
    equity_gap,
    t_interval,
    two_proportion_z_test,
    velocity,
    welch_t_test_summary,
    wilson_interval,
)


def test_wilson_interval_wraps_proportion() -> None:
    interval = wilson_interval(45, 100)
    assert interval is not None
    assert interval.lower < 0.45 < interval.upper
    assert 0.0 <= interval.lower <= 1.0
    assert 0.0 <= interval.upper <= 1.0


def test_wilson_interval_handles_zero_denominator() -> None:
    assert wilson_interval(0, 0) is None


def test_t_interval_wraps_mean() -> None:
    interval = t_interval(mean=10.0, std=2.0, n=30)
    assert isinstance(interval, Interval)
    assert interval.lower < 10.0 < interval.upper


def test_t_interval_requires_variance() -> None:
    assert t_interval(mean=10.0, std=0.0, n=30) is None
    assert t_interval(mean=10.0, std=2.0, n=1) is None


def test_equity_gap_identifies_best_and_worst() -> None:
    gap = equity_gap({"girls": 0.6, "boys": 0.4, "other": 0.5})
    assert gap is not None
    assert gap["best_group"] == "girls"
    assert gap["worst_group"] == "boys"
    assert gap["gap"] == pytest.approx(0.2)


def test_equity_gap_needs_two_groups() -> None:
    assert equity_gap({"only": 0.5}) is None
    assert equity_gap({"a": None, "b": None}) is None


def test_velocity_fits_a_slope_and_projects() -> None:
    result = velocity([0.1, 0.2, 0.3], target=0.5)
    assert result is not None
    assert result["slope_per_round"] == pytest.approx(0.1)
    assert result["next_round_projection"] == pytest.approx(0.4)
    assert result["rounds_to_target"] == pytest.approx(2.0)


def test_velocity_flat_series_has_no_time_to_target() -> None:
    result = velocity([0.3, 0.3, 0.3], target=0.5)
    assert result is not None
    assert result["slope_per_round"] == pytest.approx(0.0)
    assert "rounds_to_target" not in result


def test_two_proportion_z_test_detects_difference() -> None:
    result = two_proportion_z_test(x1=20, n1=100, x2=60, n2=100)
    assert result is not None
    assert result["p_value"] < 0.001
    assert result["diff"] == pytest.approx(0.4)


def test_welch_t_test_summary_matches_hand_calc() -> None:
    result = welch_t_test_summary(mean1=10.0, std1=2.0, n1=30, mean2=12.0, std2=2.0, n2=30)
    assert result is not None
    assert result["p_value"] < 0.001
    assert result["diff"] == pytest.approx(2.0)
