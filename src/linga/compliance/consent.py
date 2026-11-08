"""Consent column checker.

Looks for the consent column named in ``linga.yml`` (``consent_column``).
Reports:

- whether the column is present,
- how many rows recorded a positive consent value,
- how many did not (and would be excluded with ``--exclude``).

If ``--exclude`` is set, writes a filtered CSV alongside the input with
``_consented`` appended to the stem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from linga.config import load_linga_config
from linga.errors import LingaError

POSITIVE_VALUES: frozenset[str] = frozenset({"yes", "y", "true", "1", "consent"})


@dataclass
class ConsentReport:
    column: str | None
    total_rows: int
    consented: int
    non_consented: int
    filtered_path: Path | None = None

    def summary(self) -> str:
        if self.column is None:
            return (
                "[red]No consent column configured.[/red] "
                "Add `consent_column: <name>` to linga.yml."
            )
        lines = [
            f"Consent column: [cyan]{self.column}[/cyan]",
            f"Total rows: {self.total_rows}",
            f"Consented: [green]{self.consented}[/green]",
            f"Non-consented: [yellow]{self.non_consented}[/yellow]",
        ]
        if self.filtered_path is not None:
            lines.append(f"Wrote filtered CSV: {self.filtered_path}")
        return "\n".join(lines)


def _positive(value: object) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in POSITIVE_VALUES


def check_consent(
    project_dir: Path,
    data_path: Path,
    exclude: bool = False,
) -> ConsentReport:
    """Check consent on ``data_path``. Optionally write a filtered CSV."""

    cfg_path = Path(project_dir) / "linga.yml"
    if not cfg_path.exists():
        raise LingaError(
            "No linga.yml found in the project directory.",
            suggest="Run `linga init` first.",
        )
    cfg = load_linga_config(cfg_path)

    df = pd.read_csv(data_path)
    column = cfg.consent_column
    if column is None or column not in df.columns:
        return ConsentReport(
            column=None if column is None else column,
            total_rows=len(df),
            consented=0,
            non_consented=len(df),
        )

    mask = df[column].map(_positive)
    consented = int(mask.sum())
    non_consented = len(df) - consented

    filtered_path: Path | None = None
    if exclude and non_consented > 0:
        filtered_path = data_path.with_name(f"{data_path.stem}_consented.csv")
        df.loc[mask].to_csv(filtered_path, index=False)

    return ConsentReport(
        column=column,
        total_rows=len(df),
        consented=consented,
        non_consented=non_consented,
        filtered_path=filtered_path,
    )
