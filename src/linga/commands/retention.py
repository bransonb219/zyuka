"""`linga retention …` — retention policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def check(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    data_dir: Annotated[
        Path,
        typer.Option("--data", help="Directory to scan for old files."),
    ] = Path("outputs"),
) -> None:
    """Report files older than the configured retention period."""

    from linga.rights.retention import list_expired

    expired = list_expired(project_dir=project, data_dir=data_dir)
    table = Table(title="Retention — expired files")
    table.add_column("Path")
    table.add_column("Age (days)", justify="right")
    for item in expired:
        table.add_row(str(item.path), str(item.age_days))
    console.print(table)


def purge(
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    data_dir: Annotated[Path, typer.Option("--data", help="Directory to purge.")] = Path("outputs"),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete expired files after confirmation."""

    from linga.rights.retention import list_expired, purge_expired

    expired = list_expired(project_dir=project, data_dir=data_dir)
    if not expired:
        console.print("Nothing to purge.")
        return

    for item in expired:
        console.print(f"- {item.path}  ({item.age_days} days)")
    if not yes and not typer.confirm("Delete these files?"):
        raise typer.Abort()

    purge_expired(project_dir=project, files=[item.path for item in expired])
    console.print(f"[green]Purged {len(expired)} file(s).[/green]")
