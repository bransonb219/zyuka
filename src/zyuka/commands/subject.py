"""`zyuka subject …` — data-subject access and erasure."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def find(
    identifier: Annotated[str, typer.Option("--id", help="Raw identifier (e.g. NRC).")],
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    data_dir: Annotated[
        Path,
        typer.Option("--data", help="Directory of protected datasets."),
    ] = Path("outputs/protected"),
) -> None:
    """List protected files containing the pseudonymised form of ``--id``."""

    from zyuka.rights.subject import find_subject

    matches = find_subject(project_dir=project, data_dir=data_dir, identifier=identifier)
    if not matches:
        console.print("No matches.")
        return
    for m in matches:
        console.print(f"- {m.path}  ({m.row_count} rows)")


def erase(
    identifier: Annotated[str, typer.Option("--id", help="Raw identifier (e.g. NRC).")],
    project: Annotated[Path, typer.Option("--project", help="Project directory.")] = Path("."),
    data_dir: Annotated[
        Path,
        typer.Option("--data", help="Directory of protected datasets."),
    ] = Path("outputs/protected"),
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Remove rows for a subject from all protected datasets and audit the action."""

    from zyuka.rights.subject import erase_subject

    if not yes and not typer.confirm(f"Erase subject {identifier!r} from {data_dir}?"):
        raise typer.Abort()

    report = erase_subject(project_dir=project, data_dir=data_dir, identifier=identifier)
    console.print(
        f"[green]Erased {report.rows_removed} rows across {len(report.files)} files.[/green]"
    )
