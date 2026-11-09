"""Data-subject access and erasure requests.

Protected datasets never contain raw identifiers — they contain the HMAC
pseudonym of each identifier. To honour access/erasure requests we take the
raw identifier from the data subject, pseudonymise it with the project's
key, then search every protected CSV for rows whose identifier columns
match that pseudonym.

The search is strict: an exact string match on any pseudonymised column.
Erasure writes the file back with those rows removed and appends an
audit entry describing how many rows were removed from each file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from zyuka.config import load_zyuka_config
from zyuka.errors import ZyukaError
from zyuka.privacy.pseudonymise import pseudonymise_value
from zyuka.security.audit import write_entry
from zyuka.security.keys import Key, load_key

PSEUDONYM_COLUMN_HINTS: tuple[str, ...] = ("nrc", "phone", "pid", "respondent", "subject_id")


@dataclass
class SubjectMatch:
    path: Path
    row_count: int
    matched_columns: list[str] = field(default_factory=list)


@dataclass
class ErasureReport:
    rows_removed: int
    files: list[Path]


def _load_project_key(project_dir: Path) -> Key:
    cfg_path = Path(project_dir) / "zyuka.yml"
    if not cfg_path.exists():
        raise ZyukaError(
            "No zyuka.yml found in the project directory.",
            suggest="Run `zyuka init` first.",
        )
    config = load_zyuka_config(cfg_path)
    if not Path(config.key_path).exists():
        raise ZyukaError(
            f"Key file is missing at {config.key_path}.",
            suggest="Run `zyuka key generate` to create one.",
        )
    return load_key(config.key_path)


def _identifier_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if any(h in c.lower() for h in PSEUDONYM_COLUMN_HINTS)]


def _protected_csvs(data_dir: Path) -> list[Path]:
    return sorted(Path(data_dir).glob("protected_*.csv"))


def find_subject(
    project_dir: Path,
    data_dir: Path,
    identifier: str,
) -> list[SubjectMatch]:
    """Return which protected files contain the pseudonym of ``identifier``."""

    key = _load_project_key(project_dir)
    pseudonym = pseudonymise_value(identifier, key.material)

    matches: list[SubjectMatch] = []
    for path in _protected_csvs(data_dir):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        cols = _identifier_columns(df)
        if not cols:
            continue
        mask = pd.Series(False, index=df.index)
        hit_cols: list[str] = []
        for col in cols:
            col_hits = df[col] == pseudonym
            if col_hits.any():
                hit_cols.append(col)
                mask = mask | col_hits
        if mask.any():
            matches.append(
                SubjectMatch(path=path, row_count=int(mask.sum()), matched_columns=hit_cols)
            )
    return matches


def erase_subject(
    project_dir: Path,
    data_dir: Path,
    identifier: str,
) -> ErasureReport:
    """Remove rows for a subject and append an audit entry for the action."""

    key = _load_project_key(project_dir)
    pseudonym = pseudonymise_value(identifier, key.material)

    files_touched: list[Path] = []
    total_removed = 0
    audit_log = Path(project_dir) / ".zyuka" / "audit.jsonl"

    for path in _protected_csvs(data_dir):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        cols = _identifier_columns(df)
        if not cols:
            continue
        mask = pd.Series(False, index=df.index)
        for col in cols:
            mask = mask | (df[col] == pseudonym)
        if not mask.any():
            continue
        removed = int(mask.sum())
        df.loc[~mask].to_csv(path, index=False)
        total_removed += removed
        files_touched.append(path)
        write_entry(
            audit_log,
            command="subject.erase",
            inputs=[path],
            outputs=[path],
            rows=removed,
            columns=len(df.columns),
            settings={"key_fingerprint": key.fingerprint, "subject_hash": pseudonym},
        )
    return ErasureReport(rows_removed=total_removed, files=files_touched)
