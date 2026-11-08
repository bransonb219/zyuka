"""Deterministic Faker-based synthetic data generator.

Produces three survey rounds (baseline, midline, endline) with shape and
column names resembling a Kobo / ODK export. Includes columns that the PII
scanner and quality checks are expected to flag so the demo exercises the
full pipeline. **Never** uses real respondent data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

ROUND_NAMES: tuple[str, ...] = ("baseline", "midline", "endline")

ZM_PROVINCES: tuple[str, ...] = (
    "Central",
    "Copperbelt",
    "Eastern",
    "Lusaka",
    "Muchinga",
    "Northern",
    "North-Western",
    "Southern",
    "Western",
    "Luapula",
)

ENUMERATORS: tuple[str, ...] = ("E01", "E02", "E03", "E04", "E05")


@dataclass(frozen=True)
class SyntheticOptions:
    rows_per_round: int = 180
    seed: int = 20260101
    start_date: date = date(2026, 1, 15)


def _fake_nrc(rng: np.random.Generator) -> str:
    """A Faker-only Zambian NRC-shaped identifier. Deterministic from rng."""

    serial = int(rng.integers(100000, 999999))
    region = int(rng.integers(1, 99))
    check = int(rng.integers(1, 9))
    return f"{serial:06d}/{region:02d}/{check}"


def _fake_phone(rng: np.random.Generator) -> str:
    prefix = int(rng.integers(0, 2))  # 0 => 097x, 1 => 096x
    body = int(rng.integers(0, 99_999_999))
    return f"09{7 if prefix == 0 else 6}{body:08d}"


def generate_round(round_name: str, options: SyntheticOptions | None = None) -> pd.DataFrame:
    """Generate one round of synthetic survey data."""

    opts = options or SyntheticOptions()
    if round_name not in ROUND_NAMES:
        raise ValueError(f"unknown round: {round_name!r}; expected one of {ROUND_NAMES}")

    round_index = ROUND_NAMES.index(round_name)
    seed = opts.seed + round_index * 1009
    fake = Faker("en_GB")
    fake.seed_instance(seed)
    rng = np.random.default_rng(seed)

    start = opts.start_date + timedelta(days=round_index * 180)

    rows: list[dict[str, object]] = []
    for i in range(opts.rows_per_round):
        pid_seed = f"P{i:04d}"  # stable across rounds, so linkage works
        age = int(rng.integers(5, 85))
        dob_year = start.year - age
        dob = date(dob_year, int(rng.integers(1, 13)), int(rng.integers(1, 28)))
        sex = str(rng.choice(["female", "male"], p=[0.52, 0.48]))
        province = str(rng.choice(ZM_PROVINCES))
        enumerator = str(rng.choice(ENUMERATORS))

        interview_start = datetime.combine(
            start + timedelta(days=int(rng.integers(0, 150))),
            datetime.min.time(),
        ) + timedelta(hours=int(rng.integers(7, 18)), minutes=int(rng.integers(0, 60)))
        duration_minutes = int(rng.integers(3, 55))
        interview_end = interview_start + timedelta(minutes=duration_minutes)

        trained = bool(rng.random() < (0.3 + round_index * 0.2))
        has_income_source = bool(rng.random() < (0.4 + round_index * 0.15))
        income = float(rng.normal(1500 + round_index * 400, 600))
        income = max(0.0, round(income, 2))

        services = rng.choice(["health", "education", "wash", "livelihoods"], size=2, replace=False)
        services_str = " ".join(services)

        has_disability = bool(rng.random() < 0.08)
        hiv_status_known = bool(rng.random() < 0.6)
        marital = str(
            rng.choice(
                ["single", "married", "widowed", "divorced"],
                p=[0.3, 0.55, 0.1, 0.05],
            )
        )

        consent = bool(rng.random() < 0.98)
        gps_lat = float(-15.0 + rng.normal(0, 2.0))
        gps_lon = float(28.0 + rng.normal(0, 2.0))

        rows.append(
            {
                "_uuid": fake.uuid4(),
                "instanceID": f"uuid:{fake.uuid4()}",
                "pid_seed": pid_seed,
                "respondent_name": fake.name(),
                "nrc": _fake_nrc(rng),
                "phone": _fake_phone(rng),
                "email": fake.email() if rng.random() < 0.3 else "",
                "dob": dob.isoformat(),
                "age": age,
                "sex": sex,
                "province": province,
                "district": fake.city(),
                "address_text": fake.street_address(),
                "gps_lat": round(gps_lat, 6),
                "gps_lon": round(gps_lon, 6),
                "demographics/consent": "yes" if consent else "no",
                "demographics/marital_status": marital,
                "demographics/has_disability": "yes" if has_disability else "no",
                "health/hiv_status_known": "yes" if hiv_status_known else "no",
                "livelihoods/has_income_source": "yes" if has_income_source else "no",
                "livelihoods/monthly_income_zmw": income,
                "training/attended": "yes" if trained else "no",
                "services_used": services_str,
                "enumerator_id": enumerator,
                "start": interview_start.isoformat(timespec="seconds"),
                "end": interview_end.isoformat(timespec="seconds"),
                "notes": "",
                "round": round_name,
            }
        )

    df = pd.DataFrame(rows)
    # Inject a couple of deliberate quality issues so `linga check` has work.
    if len(df) > 20:
        dup = df.iloc[0].copy()
        df = pd.concat([df, pd.DataFrame([dup])], ignore_index=True)
    if len(df) > 5:
        df.loc[3, "livelihoods/monthly_income_zmw"] = 10_000_000.0
        df.loc[4, "age"] = -1
        df.loc[5, "demographics/consent"] = "no"
    return df


def generate_all_rounds(options: SyntheticOptions | None = None) -> dict[str, pd.DataFrame]:
    return {name: generate_round(name, options) for name in ROUND_NAMES}


def write_rounds(out_dir: Path, options: SyntheticOptions | None = None) -> dict[str, Path]:
    """Write one CSV per round under ``out_dir`` and return the file paths."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, df in generate_all_rounds(options).items():
        path = out_dir / f"survey_{name}.csv"
        df.to_csv(path, index=False)
        paths[name] = path
    return paths
