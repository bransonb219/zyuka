"""`zyuka eda` — profile a round and write a JSON snapshot.

The snapshot contains only derived statistics (dtypes, missingness,
moments, top values, pairwise Pearson r). No raw rows are written so
the file is safe to share alongside donor reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from zyuka.analysis.eda import profile_dataframe

console = Console()


def eda(
    data: Annotated[Path, typer.Argument(help="CSV or XLSX export.")],
    project: Annotated[
        Path,
        typer.Option("--project", help="Project directory (contains zyuka.yml)."),
    ] = Path("."),
    round_name: Annotated[str, typer.Option("--round", help="Round name.")] = "baseline",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Where to write eda_{round}.json."),
    ] = None,
) -> None:
    """Profile the dataset for exploratory analysis."""

    from zyuka.ingest.rounds import load_round

    df = load_round(data, round_name)
    profile = profile_dataframe(df)

    out_dir = project / "outputs" / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out or out_dir / f"eda_{round_name}.json"
    out_path.write_text(json.dumps(profile.to_dict(), indent=2, default=str), encoding="utf-8")

    table = Table(title="Dataset profile")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Rows", f"{profile.n_rows:,}")
    table.add_row("Columns", str(profile.n_cols))
    table.add_row("Duplicate rows", str(profile.duplicate_rows))
    for kind in ("numeric", "categorical", "text", "datetime"):
        table.add_row(f"  {kind}", str(len(profile.by_kind(kind))))
    console.print(table)

    if not profile.correlations.empty:
        corr_table = Table(title="Top numeric correlations")
        corr_table.add_column("A")
        corr_table.add_column("B")
        corr_table.add_column("r", justify="right")
        corr_table.add_column("n", justify="right")
        for _, row in profile.correlations.head(10).iterrows():
            corr_table.add_row(str(row["a"]), str(row["b"]), f"{row['r']:.3f}", str(int(row["n"])))
        console.print(corr_table)

    console.print(f"[green]Wrote[/green] {out_path}")
