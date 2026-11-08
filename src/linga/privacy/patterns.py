"""Regexes and helpers for PII detection.

Designed around Zambian identifiers:

- NRC: ``\\d{6}/\\d{2}/\\d`` (e.g. ``123456/78/1``)
- Mobile phone: ``(+?260|0)[79]\\d{8}`` after stripping spaces and dashes

Email, GPS, DOB and names use generic patterns. The scanner module uses these
regexes against column names *and* a sample of values.
"""

from __future__ import annotations

import re

NRC_RE = re.compile(r"\b\d{6}/\d{2}/\d\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
GEOPOINT_RE = re.compile(r"^-?\d{1,3}\.\d+\s+-?\d{1,3}\.\d+(\s+-?\d+\.\d+)?(\s+-?\d+\.\d+)?$")
GPS_PAIR_RE = re.compile(r"^-?\d{1,3}\.\d{4,}$")
DOB_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")


def normalise_phone(value: str) -> str:
    return re.sub(r"[\s\-\(\)\+]", "", value)


_PHONE_RE = re.compile(r"^(?:260|0)[79]\d{8}$")


def matches_phone(value: str) -> bool:
    return bool(_PHONE_RE.match(normalise_phone(value)))


def mask_phone(value: str) -> str:
    """Return a masked rendering safe for log output, e.g. ``0977****12``."""

    raw = normalise_phone(value)
    if len(raw) < 6:
        return "***"
    return raw[:4] + "****" + raw[-2:]


def mask_generic(value: str, keep: int = 2) -> str:
    """Mask any string, keeping the last ``keep`` characters."""

    s = str(value)
    if len(s) <= keep:
        return "*" * len(s)
    return "*" * (len(s) - keep) + s[-keep:]
