"""`linga check` — data quality checks on a round."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def check(
    data: Annotated[Path, typer.Argument(help="CSV or XLSX export.")],
    round_name: Annotated[str, typer.Option("--round", help="Round name.")] = "baseline",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Where to write quality_flags.csv."),
    ] = None,
) -> None:
    """Run duplicates, missingness, outliers, constraint and duration checks."""

    from linga.ingest.rounds import load_round
    from linga.quality.report import run_quality

    df = load_round(data, round_name)
    report = run_quality(df)

    table = Table(title=f"Quality — {round_name}")
    table.add_column("Check")
    table.add_column("Count", justify="right")
    for name, count in report.summary.items():
        table.add_row(name, str(count))
    console.print(table)

    out = out or (data.parent / f"quality_flags_{round_name}.csv")
    report.flags.to_csv(out, index=False)
    console.print(f"[green]Wrote[/green] {out}")
