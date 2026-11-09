"""Generalisation transforms — reduce precision instead of dropping outright.

Each helper here takes a pandas Series and returns a new Series of the same
length, so they compose cleanly in :func:`protect_dataframe`. Rules of thumb:

- Ages → 5- or 10-year bands.
- DOB → derive age, then band.
- GPS coordinates → round to N decimals, or look up the admin area.
- Free-form dates → truncate to year-month.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import pandas as pd

from zyuka.data import ZAMBIA_ADMIN_CSV

DEFAULT_AGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 4, "0-4"),
    (5, 9, "5-9"),
    (10, 14, "10-14"),
    (15, 19, "15-19"),
    (20, 24, "20-24"),
    (25, 34, "25-34"),
    (35, 49, "35-49"),
    (50, 64, "50-64"),
    (65, 200, "65+"),
)


def age_to_band(age: float | int | None) -> str:
    """Map a numeric age to a named band. Negative/NaN → ``""``."""

    if age is None or (isinstance(age, float) and pd.isna(age)):
        return ""
    try:
        a = int(age)
    except (TypeError, ValueError):
        return ""
    if a < 0:
        return ""
    for lo, hi, label in DEFAULT_AGE_BANDS:
        if lo <= a <= hi:
            return label
    return ""


def generalise_age(series: pd.Series) -> pd.Series:
    return series.map(age_to_band)


def generalise_dob(series: pd.Series, reference_year: int | None = None) -> pd.Series:
    """Convert a DOB column (string or date) to an age-band string.

    ``reference_year`` defaults to the latest year seen in the data so demo
    output is stable without depending on today's date.
    """

    dates = pd.to_datetime(series, errors="coerce")
    years = dates.dt.year
    ref = reference_year or int(years.max()) if years.notna().any() else None
    if ref is None:
        return pd.Series([""] * len(series), index=series.index)
    ages = ref - years
    return ages.map(age_to_band)


def round_coordinate(value: float | None, decimals: int = 1) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def generalise_gps(series: pd.Series, decimals: int = 1) -> pd.Series:
    return series.map(lambda v: round_coordinate(v, decimals))


def generalise_date_to_month(series: pd.Series) -> pd.Series:
    """Truncate a date column to year-month (``YYYY-MM``). Empty → ``""``."""

    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime("%Y-%m").fillna("")


@lru_cache(maxsize=1)
def _admin_table(path: Path = ZAMBIA_ADMIN_CSV) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append((row["province"].strip(), row["district"].strip()))
    return rows


def known_provinces() -> set[str]:
    return {prov.lower() for prov, _ in _admin_table()}


def known_districts() -> dict[str, str]:
    """Return ``{lowercase_district: province}``."""

    return {d.lower(): p for p, d in _admin_table()}


def lookup_admin_area(value: str | None) -> str:
    """Resolve a free-text location to a canonical province, else ``""``."""

    if not value or not isinstance(value, str):
        return ""
    v = value.strip().lower()
    if not v:
        return ""
    if v in known_provinces():
        for prov, _ in _admin_table():
            if prov.lower() == v:
                return prov
    districts = known_districts()
    if v in districts:
        return districts[v]
    return ""


def drop_free_text(series: pd.Series) -> pd.Series:
    """Replace every value with ``""`` — used for free-text/comment columns."""

    return pd.Series([""] * len(series), index=series.index, dtype="object")
