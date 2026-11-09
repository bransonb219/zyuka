"""Bundled static data: Zambia admin table and sensitive keywords."""

from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

ZAMBIA_ADMIN_CSV = DATA_DIR / "zambia_admin.csv"
SENSITIVE_KEYWORDS_YML = DATA_DIR / "sensitive_keywords.yml"
