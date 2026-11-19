"""`zyuka analyze` — suggest + run statistical tests on a round.

Default is non-interactive: the advisor runs, high-confidence tests are
executed, and results are written to ``outputs/analysis/*.json``.
``--list-only`` just prints the suggestions; ``--confidence`` tunes
which suggestions auto-run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from zyuka.analysis.advisor import suggest_analyses
from zyuka.analysis.tests import run_many

console = Console()


def analyze(
    data: Annotated[Path, typer.Argument(help="CSV or XLSX export.")],
    project: Annotated[
        Path,
        typer.Option("--project", help="Project directory (contains zyuka.yml)."),
    ] = Path("."),
    round_name: Annotated[str, typer.Option("--round", help="Round name.")] = "baseline",
    confidence: Annotated[
        float, typer.Option("--confidence", help="Auto-run tests at or above this threshold.")
    ] = 0.6,
    list_only: Annotated[
        bool,
        typer.Option("--list-only/--run", help="Only print suggestions; don't execute."),
    ] = False,
) -> None:
    """Advise on and run statistical tests for the round's data."""

    from zyuka.ingest.rounds import load_round

    df = load_round(data, round_name)
    suggestions = suggest_analyses(df)

    table = Table(title=f"Analysis suggestions · round {round_name}")
    table.add_column("Category")
    table.add_column("Test")
    table.add_column("Columns")
    table.add_column("Conf.", justify="right")
    for s in suggestions:
        table.add_row(s.category, s.name, " × ".join(s.columns), f"{s.confidence:.2f}")
    console.print(table)
    if not suggestions:
        console.print("[yellow]No suitable tests for this dataset.[/yellow]")
        return

    if list_only:
        return

    to_run = [
        {"test": s.test, "columns": s.columns} for s in suggestions if s.confidence >= confidence
    ]
    if not to_run:
        console.print(
            f"[yellow]No suggestions passed --confidence {confidence}. "
            "Try a lower threshold.[/yellow]"
        )
        return

    results = run_many(df, to_run)

    analysis_dir = project / "outputs" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    result_table = Table(title="Results")
    result_table.add_column("Test")
    result_table.add_column("Summary")
    for result in results:
        slug_cols = "_".join(result.columns)[:60]
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", f"{result.kind}_{slug_cols}")
        path = analysis_dir / f"{safe}_{round_name}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
        result_table.add_row(result.name, result.summary or "—")
        written += 1
    console.print(result_table)
    console.print(f"[green]Wrote {written} result file(s) to[/green] {analysis_dir}")
