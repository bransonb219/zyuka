"""Deterministic pseudonymisation with keyed HMAC-SHA256.

Using HMAC rather than a bare hash means an attacker in possession of the
output dataset cannot reverse the map without the key. "Deterministic" here
means: same value + same key => same pseudonym, which is what we need to link
the same person across survey rounds.
"""

from __future__ import annotations

import hashlib
import hmac

import pandas as pd


def pseudonymise_value(value: str, key: bytes, length: int = 16) -> str:
    """Return a hex pseudonym for ``value``. ``length`` is the hex-char count."""

    if not isinstance(value, str):
        value = str(value)
    digest = hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:length]


def pseudonymise_series(series: pd.Series, key: bytes, length: int = 16) -> pd.Series:
    """Pseudonymise every non-null value in ``series``.

    NaN/None/empty strings are preserved as empty strings so counts of missing
    rows stay accurate downstream.
    """

    def _hash(value: object) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        s = str(value).strip()
        if s == "":
            return ""
        return pseudonymise_value(s, key, length=length)

    return series.map(_hash)
