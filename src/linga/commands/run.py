"""`linga run` — full pipeline on a configured project."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def run(
    round_name: Annotated[
        str, typer.Option("--round", help="Round to process (baseline / midline / endline).")
    ] = "baseline",
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    encrypt: Annotated[bool, typer.Option("--encrypt", help="Encrypt outputs.")] = False,
    open_report: Annotated[bool, typer.Option("--open", help="Open the HTML report.")] = False,
) -> None:
    """Run check → scan → protect → compute → report → audit."""

    from linga.pipeline import run_pipeline

    result = run_pipeline(
        project_dir=project,
        round_name=round_name,
        encrypt=encrypt,
        open_report=open_report,
    )
    console.print(f"[green]Pipeline complete.[/green] Report: {result.report_html}")
