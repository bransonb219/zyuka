"""`linga docs …` — compliance document generators."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def dpia(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    scan_json: Annotated[
        Path | None,
        typer.Option("--scan", help="PII scan JSON (optional, pre-fills fields)."),
    ] = None,
    out: Annotated[Path, typer.Option("--out", help="Output directory.")] = Path("outputs/dpia"),
) -> None:
    """Write a DPIA starter (Markdown + HTML) pre-filled from scan + config."""

    from linga.compliance.dpia import render_dpia

    paths = render_dpia(project_dir=project, scan_json=scan_json, out_dir=out)
    for p in paths:
        console.print(f"[green]Wrote[/green] {p}")


def consent(
    data: Annotated[Path, typer.Argument(help="Dataset to check consent on.")],
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    exclude: Annotated[
        bool,
        typer.Option("--exclude", help="Exclude rows without consent and write a filtered CSV."),
    ] = False,
) -> None:
    """Check that a consent field is present and (optionally) filter out non-consent."""

    from linga.compliance.consent import check_consent

    report = check_consent(project_dir=project, data_path=data, exclude=exclude)
    console.print(report.summary())
