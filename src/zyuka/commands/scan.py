"""`zyuka scan` — PII and sensitive-field scanner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def scan(
    data: Annotated[Path, typer.Argument(help="CSV or XLSX export.")],
    out: Annotated[Path | None, typer.Option("--out", help="Write scan report JSON here.")] = None,
) -> None:
    """Scan ``data`` for PII and sensitive fields."""

    from zyuka.ingest.rounds import read_table
    from zyuka.privacy.scanner import scan_dataframe

    df = read_table(data)
    report = scan_dataframe(df)

    table = Table(title=f"PII scan — {data.name}")
    table.add_column("Column")
    table.add_column("Risk")
    table.add_column("Signals")
    table.add_column("Suggested action")
    for col in report.columns:
        table.add_row(col.name, col.risk, ", ".join(col.signals), col.suggested_action)
    console.print(table)

    if out:
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out}")
