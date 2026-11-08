"""`linga report` — render HTML + Excel."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def report(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    results: Annotated[
        Path,
        typer.Option("--results", help="Indicator results JSON produced by `linga compute`."),
    ] = Path("outputs/indicator_results.json"),
    out_dir: Annotated[
        Path, typer.Option("--out", help="Where to write report.html and iptt.xlsx.")
    ] = Path("outputs/report"),
    open_report: Annotated[bool, typer.Option("--open", help="Open HTML report.")] = False,
) -> None:
    """Render HTML + Excel from indicator results."""

    from linga.reports.pipeline import render_report

    html_path = render_report(
        project_dir=project,
        results_json=results,
        out_dir=out_dir,
        open_report=open_report,
    )
    console.print(f"[green]Wrote[/green] {html_path}")
